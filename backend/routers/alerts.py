from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import Optional

from core.database import get_db, fetchall, fetchone, execute
from core.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])


class AlertIn(BaseModel):
    device_id:       int
    sensor_id:       Optional[int] = None
    severity:        str = "warning"
    title:           str
    description:     Optional[str] = None
    threshold_value: Optional[float] = None
    actual_value:    Optional[float] = None

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in ("critical", "warning", "info"):
            raise ValueError("severity must be critical, warning, or info")
        return v


_BASE_SQL = """
    SELECT
        a.*,
        d.name        AS device_name,
        d.device_type,
        r.room_number,
        f.floor_number,
        b.name        AS building_name
    FROM   Alerts    a
    JOIN   Devices   d  ON d.device_id   = a.device_id
    JOIN   Rooms     r  ON r.room_id     = d.room_id
    JOIN   Floors    f  ON f.floor_id    = r.floor_id
    JOIN   Buildings b  ON b.building_id = f.building_id
    WHERE  1=1
"""


def _build_filters(
    building_id: Optional[int],
    severity:    Optional[str],
    status:      Optional[str],
) -> tuple[str, list]:
    sql, params = "", []
    if building_id is not None:
        sql += " AND b.building_id = %s"
        params.append(building_id)
    if severity:
        sql += " AND a.severity = %s"
        params.append(severity)
    if status:
        sql += " AND a.status = %s"
        params.append(status)
    return sql, params


@router.get("")
def list_alerts(
    building_id: Optional[int] = Query(None),
    severity:    Optional[str] = Query(None, pattern="^(critical|warning|info)$"),
    status:      Optional[str] = Query(None, pattern="^(active|resolved|dismissed)$"),
    page:        int = Query(1,  ge=1),
    page_size:   int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    filter_sql, params = _build_filters(building_id, severity, status)
    base = _BASE_SQL + filter_sql

    total = fetchone(
        db,f"SELECT COUNT(*) AS n FROM ({base}) AS _sub",
        tuple(params),
    )["n"]

    data_sql = (
        base
        + " ORDER BY FIELD(a.status,'active','resolved','dismissed'), a.triggered_at DESC"
        + " LIMIT %s OFFSET %s"
    )
    data_params = tuple(params) + (page_size, (page - 1) * page_size)

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "items":     fetchall(db, data_sql, data_params),
    }


@router.get("/count")
def alert_count(db=Depends(get_db), _=Depends(get_current_user)):
    row = fetchone(db, """
        SELECT
            COUNT(*)                                                AS total,
            SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical,
            SUM(CASE WHEN severity = 'warning'  THEN 1 ELSE 0 END) AS warning
        FROM Alerts
        WHERE status = 'active'
    """) or {"total": 0, "critical": 0, "warning": 0}
    return {
        "total":    int(row["total"]    or 0),
        "critical": int(row["critical"] or 0),
        "warning":  int(row["warning"]  or 0),
    }


@router.get("/{alert_id}")
def get_alert(alert_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    a = fetchone(db, "SELECT * FROM Alerts WHERE alert_id = %s", (alert_id,))
    if not a:
        raise HTTPException(404, "Alert not found")
    return a


@router.post("", status_code=201)
def create_alert(body: AlertIn, db=Depends(get_db), _=Depends(get_current_user)):
    if not fetchone(db, "SELECT device_id FROM Devices WHERE device_id = %s", (body.device_id,)):
        raise HTTPException(404, "Device not found")
    aid = execute(
        db,
        """
        INSERT INTO Alerts
            (device_id, sensor_id, severity, title, description,
             threshold_value, actual_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            body.device_id, body.sensor_id, body.severity, body.title,
            body.description, body.threshold_value, body.actual_value,
        ),
    )
    return fetchone(db, "SELECT * FROM Alerts WHERE alert_id = %s", (aid,))


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    a = fetchone(db, "SELECT status FROM Alerts WHERE alert_id = %s", (alert_id,))
    if not a:
        raise HTTPException(404, "Alert not found")
    if a["status"] != "active":
        raise HTTPException(400, f"Alert is already {a['status']}")
    execute(
        db,
        "UPDATE Alerts SET status='resolved', resolved_at=NOW(), resolved_by=%s WHERE alert_id=%s",
        (int(user["sub"]), alert_id),
    )
    return {"alert_id": alert_id, "status": "resolved", "message": "Alert resolved successfully"}


@router.post("/{alert_id}/dismiss")
def dismiss_alert(alert_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    a = fetchone(db, "SELECT status FROM Alerts WHERE alert_id = %s", (alert_id,))
    if not a:
        raise HTTPException(404, "Alert not found")
    if a["status"] != "active":
        raise HTTPException(400, f"Alert is already {a['status']}")
    execute(db, "UPDATE Alerts SET status='dismissed' WHERE alert_id = %s", (alert_id,))
    return {"alert_id": alert_id, "status": "dismissed"}


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    if not fetchone(db, "SELECT alert_id FROM Alerts WHERE alert_id = %s", (alert_id,)):
        raise HTTPException(404, "Alert not found")
    execute(db, "DELETE FROM Alerts WHERE alert_id = %s", (alert_id,))