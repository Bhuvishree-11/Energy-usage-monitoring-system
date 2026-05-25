# main.py  –  FastAPI backend  ·  Energy Monitoring System
# Database : MySQL (mysql-connector-python)
# Run      : uvicorn main:app --reload

import hashlib
import os
from datetime import datetime, date, timedelta
from typing import Optional, List

import jwt
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

load_dotenv()   # reads .env if present

# ─────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────
app = FastAPI(title="Energy Monitor API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY           = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM            = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 480))  # 8 hrs

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────────────────────
# MySQL connection helper  (per-request, yielded as dependency)
# ─────────────────────────────────────────────────────────────
def get_db():
    conn = mysql.connector.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", 3306)),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", ""),
        database = os.getenv("DB_NAME",     "energy_monitor"),
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


def query(conn, sql: str, params=None) -> list[dict]:
    """Run a SELECT and return all rows as dicts."""
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows


def execute(conn, sql: str, params=None) -> int:
    """Run an INSERT / UPDATE / DELETE; commit; return lastrowid."""
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    lid = cur.lastrowid
    cur.close()
    return lid


# ─────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ─────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    name: str
    role: str
    building_id: Optional[int]

class BuildingOut(BaseModel):
    building_id: int
    building_name: str
    city: str
    building_type: str
    total_floors: int

class FloorOut(BaseModel):
    floor_id: int
    building_id: int
    floor_number: int
    number_of_rooms: int

class RoomOut(BaseModel):
    room_id: int
    floor_id: int
    room_number: str
    room_type: str
    area_sqft: float
    occupancy_status: str

class DeviceOut(BaseModel):
    device_id: int
    room_id: int
    device_name: str
    device_type: str
    power_rating_watts: float
    device_status: str

class EnergyUsageOut(BaseModel):
    usage_id: int
    device_id: int
    sensor_id: Optional[int]
    timestamp: datetime
    energy_consumed_kwh: float
    voltage: Optional[float]
    current_ampere: Optional[float]

class AlertOut(BaseModel):
    alert_id: int
    device_id: int
    alert_type: str
    alert_message: str
    threshold_value: Optional[float]
    triggered_time: datetime
    status: str

class AlertUpdate(BaseModel):
    status: str   # 'resolved' | 'dismissed'

class ReportOut(BaseModel):
    report_id: int
    building_id: int
    report_date: date
    total_energy_kwh: float
    carbon_emission_estimate: Optional[float]

class DashboardStats(BaseModel):
    total_energy_today_kwh: float
    active_devices: int
    active_alerts: int
    carbon_today_kg: float
    hourly_usage: List[dict]
    room_usage: List[dict]

class AddUsageBody(BaseModel):
    device_id: int
    sensor_id: Optional[int] = None
    energy_kwh: float
    voltage: Optional[float] = None
    current_ampere: Optional[float] = None


# ─────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    rows = query(db, "SELECT * FROM User WHERE email = %s", (form.username,))
    if not rows or rows[0]["password"] != hash_password(form.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user  = rows[0]
    token = create_token({"sub": str(user["user_id"]), "role": user["role"]})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      user["user_id"],
        "name":         user["name"],
        "role":         user["role"],
        "building_id":  user["building_id"],
    }


# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────
@app.get("/dashboard/{building_id}", response_model=DashboardStats)
def dashboard(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    energy = query(db, """
        SELECT COALESCE(SUM(eu.energy_consumed_kwh), 0) AS total
        FROM Energy_Usage eu
        JOIN Device d ON d.device_id = eu.device_id
        JOIN Room   r ON r.room_id   = d.room_id
        JOIN Floor  f ON f.floor_id  = r.floor_id
        WHERE f.building_id = %s AND DATE(eu.timestamp) = CURDATE()
    """, (building_id,))
    total_kwh = float(energy[0]["total"])

    devices = query(db, """
        SELECT COUNT(*) AS cnt FROM Device d
        JOIN Room  r ON r.room_id  = d.room_id
        JOIN Floor f ON f.floor_id = r.floor_id
        WHERE f.building_id = %s AND d.device_status = 'active'
    """, (building_id,))

    alerts = query(db, """
        SELECT COUNT(*) AS cnt FROM Alert a
        JOIN Device d ON d.device_id = a.device_id
        JOIN Room   r ON r.room_id   = d.room_id
        JOIN Floor  f ON f.floor_id  = r.floor_id
        WHERE f.building_id = %s AND a.status = 'active'
    """, (building_id,))

    hourly = query(db, """
        SELECT HOUR(eu.timestamp)                  AS hour,
            ROUND(SUM(eu.energy_consumed_kwh), 3) AS kwh
        FROM Energy_Usage eu
        JOIN Device d ON d.device_id = eu.device_id
        JOIN Room   r ON r.room_id   = d.room_id
        JOIN Floor  f ON f.floor_id  = r.floor_id
        WHERE f.building_id = %s
        AND eu.timestamp >= NOW() - INTERVAL 12 HOUR
        GROUP BY HOUR(eu.timestamp)
        ORDER BY hour
    """, (building_id,))

    room_usage = query(db, """
        SELECT r.room_number, r.room_type,
            ROUND(SUM(eu.energy_consumed_kwh), 3) AS kwh
        FROM Energy_Usage eu
        JOIN Device d ON d.device_id = eu.device_id
        JOIN Room   r ON r.room_id   = d.room_id
        JOIN Floor  f ON f.floor_id  = r.floor_id
        WHERE f.building_id = %s AND DATE(eu.timestamp) = CURDATE()
        GROUP BY r.room_id, r.room_number, r.room_type
        ORDER BY kwh DESC
    """, (building_id,))

    return {
        "total_energy_today_kwh": total_kwh,
        "active_devices":         devices[0]["cnt"],
        "active_alerts":          alerts[0]["cnt"],
        "carbon_today_kg":        round(total_kwh * 0.46, 3),
        "hourly_usage":           [dict(r) for r in hourly],
        "room_usage":             [dict(r) for r in room_usage],
    }


# ─────────────────────────────────────────────────────────────
# BUILDINGS
# ─────────────────────────────────────────────────────────────
@app.get("/buildings", response_model=List[BuildingOut])
def get_buildings(db=Depends(get_db), _=Depends(get_current_user)):
    return query(db, "SELECT * FROM Building")


@app.get("/buildings/{building_id}/floors", response_model=List[FloorOut])
def get_floors(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return query(db, "SELECT * FROM Floor WHERE building_id = %s", (building_id,))


# ─────────────────────────────────────────────────────────────
# ROOMS
# ─────────────────────────────────────────────────────────────
@app.get("/floors/{floor_id}/rooms", response_model=List[RoomOut])
def get_rooms(floor_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return query(db, "SELECT * FROM Room WHERE floor_id = %s", (floor_id,))


# ─────────────────────────────────────────────────────────────
# DEVICES
# ─────────────────────────────────────────────────────────────
@app.get("/rooms/{room_id}/devices", response_model=List[DeviceOut])
def get_room_devices(room_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return query(db, "SELECT * FROM Device WHERE room_id = %s", (room_id,))


@app.get("/buildings/{building_id}/devices", response_model=List[DeviceOut])
def get_building_devices(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return query(db, """
        SELECT d.* FROM Device d
        JOIN Room  r ON r.room_id  = d.room_id
        JOIN Floor f ON f.floor_id = r.floor_id
        WHERE f.building_id = %s
    """, (building_id,))


# ─────────────────────────────────────────────────────────────
# ENERGY USAGE
# ─────────────────────────────────────────────────────────────
@app.get("/devices/{device_id}/usage", response_model=List[EnergyUsageOut])
def get_device_usage(device_id: int, limit: int = 50,
                    db=Depends(get_db), _=Depends(get_current_user)):
    return query(db,
        "SELECT * FROM Energy_Usage WHERE device_id = %s ORDER BY timestamp DESC LIMIT %s",
        (device_id, limit))


@app.post("/usage", status_code=201)
def add_usage(body: AddUsageBody, db=Depends(get_db), _=Depends(get_current_user)):
    uid = execute(db, """
        INSERT INTO Energy_Usage
            (device_id, sensor_id, energy_consumed_kwh, voltage, current_ampere)
        VALUES (%s, %s, %s, %s, %s)
    """, (body.device_id, body.sensor_id, body.energy_kwh, body.voltage, body.current_ampere))
    return {"usage_id": uid}


# ─────────────────────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────────────────────
@app.get("/buildings/{building_id}/alerts", response_model=List[AlertOut])
def get_alerts(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return query(db, """
        SELECT a.* FROM Alert a
        JOIN Device d ON d.device_id = a.device_id
        JOIN Room   r ON r.room_id   = d.room_id
        JOIN Floor  f ON f.floor_id  = r.floor_id
        WHERE f.building_id = %s
        ORDER BY a.triggered_time DESC
    """, (building_id,))


@app.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdate,
                db=Depends(get_db), _=Depends(get_current_user)):
    if body.status not in ("resolved", "dismissed"):
        raise HTTPException(status_code=400, detail="status must be 'resolved' or 'dismissed'")
    execute(db, "UPDATE Alert SET status = %s WHERE alert_id = %s", (body.status, alert_id))
    return {"message": "Alert updated"}


# ─────────────────────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────────────────────
@app.get("/buildings/{building_id}/reports", response_model=List[ReportOut])
def get_reports(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return query(db,
        "SELECT * FROM Energy_Report WHERE building_id = %s ORDER BY report_date DESC",
        (building_id,))


@app.post("/buildings/{building_id}/reports/generate", status_code=201)
def generate_report(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Aggregate today's Energy_Usage into Energy_Report (upserts)."""
    row = query(db, """
        SELECT ROUND(SUM(eu.energy_consumed_kwh), 4) AS total,
            MAX(eu.timestamp)                     AS peak
        FROM Energy_Usage eu
        JOIN Device d ON d.device_id = eu.device_id
        JOIN Room   r ON r.room_id   = d.room_id
        JOIN Floor  f ON f.floor_id  = r.floor_id
        WHERE f.building_id = %s AND DATE(eu.timestamp) = CURDATE()
    """, (building_id,))
    total_kwh = float(row[0]["total"] or 0)
    carbon    = round(total_kwh * 0.46, 4)
    report_id = execute(db, """
        INSERT INTO Energy_Report
            (building_id, report_date, total_energy_kwh, peak_usage_time, carbon_emission_estimate)
        VALUES (%s, CURDATE(), %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            total_energy_kwh         = VALUES(total_energy_kwh),
            peak_usage_time          = VALUES(peak_usage_time),
            carbon_emission_estimate = VALUES(carbon_emission_estimate)
    """, (building_id, total_kwh, row[0]["peak"], carbon))
    return {"report_id": report_id, "total_energy_kwh": total_kwh, "carbon_kg": carbon}


# ─────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
def home():
    return {"message": "Energy Management System Backend Running"}
