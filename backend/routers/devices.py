
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import random

from core.database import get_db, fetchall, fetchone, execute
from core.auth import get_current_user, require_admin

router = APIRouter(tags=["Devices & Sensors"])


# ── Pydantic models ─────────────────────────────────────────────

class DeviceIn(BaseModel):
    room_id: int
    name: str
    device_type: str
    power_rating_w: Optional[float] = None
    status: str = "online"
    installation_date: Optional[str] = None

class DevicePatch(BaseModel):
    name: Optional[str] = None
    device_type: Optional[str] = None
    power_rating_w: Optional[float] = None
    status: Optional[str] = None

class SensorIn(BaseModel):
    device_id: int
    sensor_type: str
    threshold_pct: float = 100.0


# ═══════════════════════════════════════════
# DEVICES
# ═══════════════════════════════════════════

@router.get("/buildings/{building_id}/devices")
def list_building_devices(
    building_id: int,
    device_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Returns device cards for the device grid.
    Supports filtering by type, status, and name search.
    Includes today_kwh and room location.
    """
    sql = """
        SELECT
            d.*,
            r.room_number,
            f.floor_number,
            b.name                                        AS building_name,
            COALESCE(ROUND(SUM(eu.energy_kwh), 3), 0)    AS today_kwh,
            COALESCE(ROUND(AVG(eu.power_kw), 3), 0)      AS avg_kw
        FROM Devices d
        JOIN Rooms r    ON r.room_id    = d.room_id
        JOIN Floors f   ON f.floor_id   = r.floor_id
        JOIN Buildings b ON b.building_id = f.building_id
        LEFT JOIN Energy_Usage eu
               ON eu.device_id = d.device_id
              AND DATE(eu.timestamp) = CURDATE()
        WHERE b.building_id = %s
    """
    params: list = [building_id]

    if device_type and device_type != "all":
        sql += " AND d.device_type = %s"
        params.append(device_type)
    if status and status != "all":
        sql += " AND d.status = %s"
        params.append(status)
    if search:
        sql += " AND d.name LIKE %s"
        params.append(f"%{search}%")

    sql += " GROUP BY d.device_id ORDER BY d.name"
    return fetchall(db, sql, tuple(params))


@router.get("/devices/{device_id}")
def get_device(device_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Single device detail with 7-day usage for the modal mini-chart."""
    device = fetchone(db, """
        SELECT d.*, r.room_number, f.floor_number, b.name AS building_name
        FROM Devices d
        JOIN Rooms r    ON r.room_id    = d.room_id
        JOIN Floors f   ON f.floor_id   = r.floor_id
        JOIN Buildings b ON b.building_id = f.building_id
        WHERE d.device_id = %s
    """, (device_id,))
    if not device:
        raise HTTPException(404, "Device not found")

    # 7-day usage for modal mini-chart
    weekly = fetchall(db, """
        SELECT DATE(timestamp) AS day, ROUND(SUM(energy_kwh), 3) AS kwh
        FROM Energy_Usage
        WHERE device_id = %s AND timestamp >= CURDATE() - INTERVAL 6 DAY
        GROUP BY DATE(timestamp)
        ORDER BY day
    """, (device_id,))

    device["weekly_chart"] = {
        "labels": [str(r["day"]) for r in weekly],
        "data":   [float(r["kwh"]) for r in weekly],
    }
    return device


@router.post("/devices", status_code=201)
def create_device(body: DeviceIn, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT room_id FROM Rooms WHERE room_id=%s", (body.room_id,)):
        raise HTTPException(404, "Room not found")
    did = execute(db,
        "INSERT INTO Devices (room_id,name,device_type,power_rating_w,status,installation_date) VALUES (%s,%s,%s,%s,%s,%s)",
        (body.room_id, body.name, body.device_type, body.power_rating_w,
         body.status, body.installation_date))
    return fetchone(db, "SELECT * FROM Devices WHERE device_id=%s", (did,))


@router.patch("/devices/{device_id}")
def update_device(device_id: int, body: DevicePatch, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT device_id FROM Devices WHERE device_id=%s", (device_id,)):
        raise HTTPException(404, "Device not found")
    updates = body.model_dump(exclude_none=True)
    if updates:
        clauses = ", ".join(f"{k}=%s" for k in updates)
        execute(db, f"UPDATE Devices SET {clauses} WHERE device_id=%s",
                (*updates.values(), device_id))
    return fetchone(db, "SELECT * FROM Devices WHERE device_id=%s", (device_id,))


@router.post("/devices/{device_id}/toggle")
def toggle_device(device_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Toggle between online/offline – used by the toggle switch in the device card."""
    device = fetchone(db, "SELECT device_id, status FROM Devices WHERE device_id=%s", (device_id,))
    if not device:
        raise HTTPException(404, "Device not found")
    if device["status"] == "faulty":
        raise HTTPException(400, "Cannot toggle a faulty device")
    new_status = "offline" if device["status"] == "online" else "online"
    execute(db, "UPDATE Devices SET status=%s WHERE device_id=%s", (new_status, device_id))
    return {"device_id": device_id, "status": new_status}


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT device_id FROM Devices WHERE device_id=%s", (device_id,)):
        raise HTTPException(404, "Device not found")
    execute(db, "DELETE FROM Devices WHERE device_id=%s", (device_id,))


# ═══════════════════════════════════════════
# SENSORS
# ═══════════════════════════════════════════

@router.get("/sensors")
def list_sensors(
    building_id: int | None = Query(None),
    sensor_type: str | None = Query(None),
    status: str | None = Query(None),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """Sensor network table – all sensors with their linked device and current load %."""
    sql = """
        SELECT
            s.*,
            d.name      AS device_name,
            d.device_type,
            d.power_rating_w,
            r.room_number,
            f.floor_number,
            b.name      AS building_name,
            CASE
                WHEN d.power_rating_w IS NULL OR d.power_rating_w = 0 THEN NULL
                ELSE ROUND(s.current_value / d.power_rating_w * 100, 1)
            END AS load_pct
        FROM Sensors s
        JOIN Devices d   ON d.device_id   = s.device_id
        JOIN Rooms r     ON r.room_id     = d.room_id
        JOIN Floors f    ON f.floor_id    = r.floor_id
        JOIN Buildings b ON b.building_id = f.building_id
        WHERE 1=1
    """
    params: list = []
    if building_id:
        sql += " AND b.building_id = %s"
        params.append(building_id)
    if sensor_type:
        sql += " AND s.sensor_type = %s"
        params.append(sensor_type)
    if status:
        sql += " AND s.status = %s"
        params.append(status)
    sql += " ORDER BY s.status DESC, b.name, f.floor_number"
    return fetchall(db, sql, tuple(params))


@router.post("/sensors", status_code=201)
def create_sensor(body: SensorIn, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT device_id FROM Devices WHERE device_id=%s", (body.device_id,)):
        raise HTTPException(404, "Device not found")
    sid = execute(db,
        "INSERT INTO Sensors (device_id,sensor_type,threshold_pct) VALUES (%s,%s,%s)",
        (body.device_id, body.sensor_type, body.threshold_pct))
    return fetchone(db, "SELECT * FROM Sensors WHERE sensor_id=%s", (sid,))


@router.post("/sensors/simulate")
def simulate_sensor_reading(
    building_id: int | None = Query(None, description="Limit simulation to one building"),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Simulate a sensor reading for every online sensor.
    Updates current_value and last_reading_at.
    Also inserts into Energy_Usage for each linked device.
    Triggers auto-alerts if reading > threshold.
    """
    sql_sensors = """
        SELECT s.*, d.power_rating_w, d.device_id, b.building_id
        FROM Sensors s
        JOIN Devices d   ON d.device_id   = s.device_id
        JOIN Rooms r     ON r.room_id     = d.room_id
        JOIN Floors f    ON f.floor_id    = r.floor_id
        JOIN Buildings b ON b.building_id = f.building_id
        WHERE s.status = 'online' AND d.status = 'online'
    """
    params: list = []
    if building_id:
        sql_sensors += " AND b.building_id = %s"
        params.append(building_id)

    sensors = fetchall(db, sql_sensors, tuple(params))
    simulated, alerts_raised = 0, 0

    for s in sensors:
        # Randomise current reading: 60–110% of rated wattage
        rated = float(s["power_rating_w"] or 1000)
        reading = round(rated * (0.60 + random.random() * 0.50), 2)
        load_pct = round(reading / rated * 100, 1)

        # Update sensor
        execute(db, """
            UPDATE Sensors
            SET current_value = %s, last_reading_at = NOW()
            WHERE sensor_id = %s
        """, (reading, s["sensor_id"]))

        # Insert energy usage log
        energy_kwh = round(reading / 1000 * (5 / 60), 6)  # 5-min interval
        voltage    = round(220 + random.uniform(0, 20), 2)
        current_a  = round(reading / voltage, 3)
        execute(db, """
            INSERT INTO Energy_Usage
                (device_id, sensor_id, energy_kwh, voltage_v, current_a, power_kw, cost_inr)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            s["device_id"], s["sensor_id"],
            energy_kwh, voltage, current_a,
            round(reading / 1000, 4),
            round(energy_kwh * 6.78, 4),
        ))

        # Auto-alert if load exceeds threshold
        threshold = float(s["threshold_pct"] or 100)
        if load_pct > threshold:
            execute(db, """
                INSERT INTO Alerts
                    (device_id, sensor_id, severity, title, description, threshold_value, actual_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                s["device_id"], s["sensor_id"],
                "critical" if load_pct > threshold * 1.1 else "warning",
                f"High Load: Sensor #{s['sensor_id']}",
                f"Reading {reading}W exceeds {threshold}% threshold ({round(rated*threshold/100)}W)",
                round(rated * threshold / 100, 2),
                reading,
            ))
            alerts_raised += 1

        simulated += 1

    return {
        "simulated": simulated,
        "alerts_raised": alerts_raised,
        "message": f"Simulated {simulated} readings, raised {alerts_raised} alerts",
    }


@router.patch("/sensors/{sensor_id}/status")
def update_sensor_status(
    sensor_id: int,
    status: str = Query(..., pattern="^(online|offline|error)$"),
    db=Depends(get_db),
    _=Depends(require_admin),
):
    if not fetchone(db, "SELECT sensor_id FROM Sensors WHERE sensor_id=%s", (sensor_id,)):
        raise HTTPException(404, "Sensor not found")
    execute(db, "UPDATE Sensors SET status=%s WHERE sensor_id=%s", (status, sensor_id))
    return {"sensor_id": sensor_id, "status": status}


@router.delete("/sensors/{sensor_id}", status_code=204)
def delete_sensor(sensor_id: int, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT sensor_id FROM Sensors WHERE sensor_id=%s", (sensor_id,)):
        raise HTTPException(404, "Sensor not found")
    execute(db, "DELETE FROM Sensors WHERE sensor_id=%s", (sensor_id,))