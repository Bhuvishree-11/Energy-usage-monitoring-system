
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import date

from core.database import get_db, fetchall, fetchone, execute
from core.auth import get_current_user, require_admin

# ═══════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════
reports_router = APIRouter(prefix="/reports", tags=["Reports"])

CARBON_FACTOR = 0.46
COST_PER_KWH  = 6.78


@reports_router.get("/{building_id}")
def list_reports(
    building_id: int,
    limit: int = Query(12, ge=1, le=60),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    b = fetchone(db, "SELECT building_id FROM Buildings WHERE building_id=%s", (building_id,))
    if not b:
        raise HTTPException(404, "Building not found")
    return fetchall(db,
        "SELECT * FROM Energy_Reports WHERE building_id=%s ORDER BY report_date DESC LIMIT %s",
        (building_id, limit))


@reports_router.post("/{building_id}/generate")
def generate_report(
    building_id: int,
    report_date: date = Query(None, description="Defaults to today"),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Auto-generate a daily summary report from Energy_Usage.
    Triggered by the 'Generate PDF Report' button.
    Calculates total kWh, peak kW, cost, carbon, and efficiency %.
    """
    if not report_date:
        report_date = date.today()

    row = fetchone(db, """
        SELECT
            COALESCE(ROUND(SUM(eu.energy_kwh), 4), 0)  AS total_kwh,
            COALESCE(ROUND(MAX(eu.power_kw), 4), 0)    AS peak_kw,
            MAX(eu.timestamp)                           AS peak_at,
            COALESCE(ROUND(SUM(eu.cost_inr), 2), 0)    AS total_cost
        FROM Energy_Usage eu
        JOIN Devices d    ON d.device_id   = eu.device_id
        JOIN Rooms r      ON r.room_id     = d.room_id
        JOIN Floors f     ON f.floor_id    = r.floor_id
        WHERE f.building_id = %s AND DATE(eu.timestamp) = %s
    """, (building_id, report_date)) or {"total_kwh": 0, "peak_kw": 0, "peak_at": None, "total_cost": 0}

    total_kwh  = float(row["total_kwh"])
    carbon_kg  = round(total_kwh * CARBON_FACTOR, 4)

    # Efficiency: compare against 30-day average
    avg = fetchone(db, """
        SELECT COALESCE(AVG(total_kwh), 0) AS avg_kwh
        FROM Energy_Reports
        WHERE building_id = %s AND report_date >= %s - INTERVAL 30 DAY
    """, (building_id, report_date)) or {"avg_kwh": 0}
    avg_kwh = float(avg["avg_kwh"]) if avg["avg_kwh"] else total_kwh or 1
    efficiency = round(min(avg_kwh / max(total_kwh, 0.001) * 100, 100), 2)

    execute(db, """
        INSERT INTO Energy_Reports
            (building_id, report_date, total_kwh, peak_kw, peak_at,
            total_cost_inr, carbon_kg, efficiency_pct)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            total_kwh       = VALUES(total_kwh),
            peak_kw         = VALUES(peak_kw),
            peak_at         = VALUES(peak_at),
            total_cost_inr  = VALUES(total_cost_inr),
            carbon_kg       = VALUES(carbon_kg),
            efficiency_pct  = VALUES(efficiency_pct)
    """, (building_id, report_date, total_kwh, row["peak_kw"], row["peak_at"],
        row["total_cost"], carbon_kg, efficiency))

    return {
        "report_date":    str(report_date),
        "total_kwh":      total_kwh,
        "peak_kw":        float(row["peak_kw"]),
        "total_cost_inr": float(row["total_cost"]),
        "carbon_kg":      carbon_kg,
        "efficiency_pct": efficiency,
        "message":        "Report generated successfully",
    }


# ═══════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════
settings_router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsPatch(BaseModel):
    global_power_threshold_kw: Optional[float] = None
    cost_per_kwh_inr:           Optional[float] = None
    carbon_factor_kg_per_kwh:   Optional[float] = None
    alert_email_enabled:        Optional[bool]  = None
    alert_sms_enabled:          Optional[bool]  = None
    auto_reports_enabled:       Optional[bool]  = None
    admin_name:                 Optional[str]   = None


def _get_all_settings(db) -> dict:
    rows = fetchall(db, "SELECT setting_key, setting_value FROM Settings WHERE user_id IS NULL")
    return {r["setting_key"]: r["setting_value"] for r in rows}


@settings_router.get("")
def get_settings(db=Depends(get_db), _=Depends(get_current_user)):
    """Load all settings for the Settings page."""
    return _get_all_settings(db)


@settings_router.patch("")
def update_settings(body: SettingsPatch, db=Depends(get_db), _=Depends(require_admin)):
    """Save Changes button."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return {"message": "Nothing to update"}

    for key, val in updates.items():
        execute(db, """
            INSERT INTO Settings (user_id, setting_key, setting_value)
            VALUES (NULL, %s, %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
        """, (key, str(val).lower() if isinstance(val, bool) else str(val)))

    return {"message": "Settings saved successfully", "updated": list(updates.keys())}


@settings_router.get("/thresholds")
def get_thresholds(db=Depends(get_db), _=Depends(get_current_user)):
    """Quick endpoint used by the alert system to fetch current thresholds."""
    s = _get_all_settings(db)
    return {
        "power_threshold_kw":   float(s.get("global_power_threshold_kw", 150)),
        "cost_per_kwh_inr":     float(s.get("cost_per_kwh_inr", 6.78)),
        "carbon_factor":        float(s.get("carbon_factor_kg_per_kwh", 0.46)),
        "email_alerts":         s.get("alert_email_enabled", "true") == "true",
        "sms_alerts":           s.get("alert_sms_enabled", "true") == "true",
        "auto_reports":         s.get("auto_reports_enabled", "false") == "true",
    }