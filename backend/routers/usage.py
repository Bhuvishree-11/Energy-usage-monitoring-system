
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime, date
import csv, io

from core.database import get_db, fetchall, fetchone, execute, executemany
from core.auth import get_current_user

router = APIRouter(prefix="/usage", tags=["Usage Records"])


class UsageIn(BaseModel):
    device_id: int
    sensor_id: Optional[int] = None
    energy_kwh: float
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    power_kw: Optional[float] = None

    @field_validator("energy_kwh")
    @classmethod
    def must_be_positive(cls, v):
        if v < 0:
            raise ValueError("energy_kwh must be ≥ 0")
        return v

class BulkUsageIn(BaseModel):
    readings: list[UsageIn]

    @field_validator("readings")
    @classmethod
    def bounded(cls, v):
        if not v:
            raise ValueError("readings cannot be empty")
        if len(v) > 500:
            raise ValueError("max 500 readings per bulk call")
        return v


@router.get("")
def list_usage(
    building_id: int | None  = Query(None),
    device_id:   int | None  = Query(None),
    start:       datetime | None = Query(None),
    end:         datetime | None = Query(None),
    page:        int = Query(1, ge=1),
    page_size:   int = Query(20, ge=1, le=200),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Paginated energy usage log for the Usage Records table.
    Returns rows with device name, location, voltage, current, kWh.
    """
    sql = """
        SELECT
            eu.usage_id,
            eu.timestamp,
            eu.energy_kwh,
            eu.voltage_v,
            eu.current_a,
            eu.power_kw,
            eu.cost_inr,
            d.name        AS device_name,
            d.device_type,
            r.room_number,
            f.floor_number,
            b.name        AS building_name
        FROM Energy_Usage eu
        JOIN Devices d    ON d.device_id   = eu.device_id
        JOIN Rooms r      ON r.room_id     = d.room_id
        JOIN Floors f     ON f.floor_id    = r.floor_id
        JOIN Buildings b  ON b.building_id = f.building_id
        WHERE 1=1
    """
    params: list = []

    if building_id:
        sql += " AND b.building_id = %s"
        params.append(building_id)
    if device_id:
        sql += " AND eu.device_id = %s"
        params.append(device_id)
    if start:
        sql += " AND eu.timestamp >= %s"
        params.append(start)
    if end:
        sql += " AND eu.timestamp <= %s"
        params.append(end)

    # Count total
    count_sql = f"SELECT COUNT(*) AS total FROM ({sql}) sub"
    count_result = fetchone(db, count_sql, tuple(params))
    total = count_result["total"] if count_result else 0

    sql += " ORDER BY eu.timestamp DESC LIMIT %s OFFSET %s"
    params += [page_size, (page - 1) * page_size]
    rows = fetchall(db, sql, tuple(params))

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pages":     (total + page_size - 1) // page_size,
        "items":     rows,
    }


@router.post("", status_code=201)
def add_usage(body: UsageIn, db=Depends(get_db), _=Depends(get_current_user)):
    if not fetchone(db, "SELECT device_id FROM Devices WHERE device_id=%s", (body.device_id,)):
        raise HTTPException(404, "Device not found")
    cost = round(body.energy_kwh * 6.78, 4)
    uid = execute(db,
        "INSERT INTO Energy_Usage (device_id,sensor_id,energy_kwh,voltage_v,current_a,power_kw,cost_inr) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (body.device_id, body.sensor_id, body.energy_kwh,
         body.voltage_v, body.current_a, body.power_kw, cost))
    return fetchone(db, "SELECT * FROM Energy_Usage WHERE usage_id=%s", (uid,))


@router.post("/bulk", status_code=201)
def add_usage_bulk(body: BulkUsageIn, db=Depends(get_db), _=Depends(get_current_user)):
    """IoT batch ingest – up to 500 readings in one request."""
    rows = [
        (r.device_id, r.sensor_id, r.energy_kwh,
         r.voltage_v, r.current_a, r.power_kw,
         round(r.energy_kwh * 6.78, 4))
        for r in body.readings
    ]
    n = executemany(db,
        "INSERT INTO Energy_Usage (device_id,sensor_id,energy_kwh,voltage_v,current_a,power_kw,cost_inr) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        rows)
    return {"inserted": n}


@router.get("/export/csv")
def export_csv(
    building_id: int | None = Query(None),
    start:       date | None = Query(None),
    end:         date | None = Query(None),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """
    CSV export – triggered by the 'Export CSV' button.
    Streams the file directly; no temp files needed.
    """
    sql = """
        SELECT
            eu.timestamp, d.name AS device, d.device_type,
            r.room_number, f.floor_number, b.name AS building,
            eu.voltage_v, eu.current_a, eu.energy_kwh, eu.cost_inr
        FROM Energy_Usage eu
        JOIN Devices d    ON d.device_id   = eu.device_id
        JOIN Rooms r      ON r.room_id     = d.room_id
        JOIN Floors f     ON f.floor_id    = r.floor_id
        JOIN Buildings b  ON b.building_id = f.building_id
        WHERE 1=1
    """
    params: list = []
    if building_id:
        sql += " AND b.building_id = %s"
        params.append(building_id)
    if start:
        sql += " AND DATE(eu.timestamp) >= %s"
        params.append(start)
    if end:
        sql += " AND DATE(eu.timestamp) <= %s"
        params.append(end)
    sql += " ORDER BY eu.timestamp DESC LIMIT 50000"

    rows = fetchall(db, sql, tuple(params))

    def generate():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "timestamp","device","device_type","room_number",
            "floor_number","building","voltage_v","current_a",
            "energy_kwh","cost_inr"
        ])
        writer.writeheader()
        yield output.getvalue()
        output.truncate(0); output.seek(0)

        for row in rows:
            writer.writerow({k: (str(v) if v is not None else "") for k, v in row.items()})
            yield output.getvalue()
            output.truncate(0); output.seek(0)

    filename = f"smartwatt_usage_{date.today()}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/summary")
def usage_summary(
    building_id: int,
    from_date:   date = Query(...),
    to_date:     date = Query(...),
    group_by:    str  = Query("day", pattern="^(hour|day|week|month)$"),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """Flexible grouped summary for custom chart ranges."""
    expr = {
        "hour":  "DATE_FORMAT(eu.timestamp,'%Y-%m-%d %H:00')",
        "day":   "DATE(eu.timestamp)",
        "week":  "YEARWEEK(eu.timestamp,1)",
        "month": "DATE_FORMAT(eu.timestamp,'%Y-%m')",
    }[group_by]

    rows = fetchall(db, f"""
        SELECT
            {expr} AS period,
            ROUND(SUM(eu.energy_kwh),4)   AS kwh,
            ROUND(AVG(eu.power_kw),4)     AS avg_kw,
            ROUND(SUM(eu.cost_inr),2)     AS cost_inr,
            COUNT(*) AS readings
        FROM Energy_Usage eu
        JOIN Devices d    ON d.device_id   = eu.device_id
        JOIN Rooms r      ON r.room_id     = d.room_id
        JOIN Floors f     ON f.floor_id    = r.floor_id
        JOIN Buildings b  ON b.building_id = f.building_id
        WHERE b.building_id = %s
          AND DATE(eu.timestamp) BETWEEN %s AND %s
        GROUP BY period
        ORDER BY period
    """, (building_id, from_date, to_date))

    return {"building_id": building_id, "group_by": group_by, "data": rows}
