
from fastapi import APIRouter, Depends, Query
from datetime import date, timedelta

from core.database import get_db, fetchall, fetchone
from core.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# India grid emission factor & Bengaluru commercial tariff
CARBON_FACTOR = 0.46   # kg CO2 per kWh
COST_PER_KWH  = 6.78   # ₹ per kWh


@router.get("/kpi")
def kpi(
    period: str = Query("month"),
    db=Depends(get_db),
    _=Depends(get_current_user)
):
    """
    KPI cards for Dashboard
    Supports: week, month, year
    """

    if period == "week":
        interval = "7 DAY"
    elif period == "month":
        interval = "30 DAY"
    elif period == "year":
        interval = "365 DAY"
    else:
        interval = "30 DAY"

    energy = fetchone(db, f"""
        SELECT COALESCE(ROUND(SUM(energy_kwh),2),0) AS total_kwh
        FROM Energy_Usage
        WHERE timestamp >= DATE_SUB(
            (SELECT MAX(timestamp) FROM Energy_Usage),
            INTERVAL {interval}
        )
    """) or {"total_kwh": 0}

    cost = fetchone(db, f"""
        SELECT COALESCE(ROUND(SUM(cost_inr),2),0) AS total_cost
        FROM Energy_Usage
        WHERE timestamp >= DATE_SUB(
            (SELECT MAX(timestamp) FROM Energy_Usage),
            INTERVAL {interval}
        )
    """) or {"total_cost": 0}

    yesterday = fetchone(db, """
        SELECT COALESCE(ROUND(SUM(energy_kwh),2),0) AS total_kwh
        FROM Energy_Usage
        WHERE DATE(timestamp)=(
            SELECT DATE(MAX(timestamp)) - INTERVAL 1 DAY
            FROM Energy_Usage
        )
    """) or {"total_kwh": 0}

    devices = fetchone(db, """
        SELECT
            SUM(CASE WHEN status='online' THEN 1 ELSE 0 END) AS online_count,
            COUNT(*) AS total_count
        FROM Devices
    """) or {"online_count": 0, "total_count": 0}

    alerts = fetchone(db, """
        SELECT COUNT(*) AS open_count
        FROM Alerts
        WHERE status='active'
    """) or {"open_count": 0}

    total_kwh = float(energy["total_kwh"])
    yesterday_kwh = float(yesterday["total_kwh"]) if yesterday["total_kwh"] else 1.0

    delta_pct = round(
        ((total_kwh - yesterday_kwh) / yesterday_kwh) * 100,
        1
    )

    return {
        "period": period,
        "total_energy_kwh": total_kwh,
        "total_energy_display": f"{total_kwh:,.0f}",
        "energy_delta_pct": delta_pct,
        "monthly_cost_inr": float(cost["total_cost"]),
        "monthly_cost_display": f"{float(cost['total_cost']):,.0f}",
        "active_devices": int(devices["online_count"] or 0),
        "total_devices": int(devices["total_count"] or 0),
        "open_alerts": int(alerts["open_count"] or 0),
        "carbon_today_kg": round(total_kwh * CARBON_FACTOR, 2)
    }

@router.get("/live-chart")
def live_chart(limit: int = Query(60, ge=10, le=200), db=Depends(get_db), _=Depends(get_current_user)):
    """
    Live real-time consumption line chart.
    Returns last `limit` readings aggregated per minute.
    """
    rows = fetchall(db, """
        SELECT
            DATE_FORMAT(timestamp, '%H:%i') AS label,
            ROUND(SUM(power_kw), 2)         AS kw
        FROM Energy_Usage
        WHERE timestamp >= NOW() - INTERVAL 3 HOUR
        GROUP BY DATE_FORMAT(timestamp, '%H:%i')
        ORDER BY MIN(timestamp) DESC
        LIMIT %s
    """, (limit,))

    rows = list(reversed(rows))
    return {
        "labels":   [r["label"] for r in rows],
        "datasets": [{"label": "kW", "data": [float(r["kw"] or 0) for r in rows]}],
    }


@router.get("/donut-chart")
def donut_chart(db=Depends(get_db), _=Depends(get_current_user)):
    """
    Energy distribution by device type (for donut chart).
    """
    rows = fetchall(db, """
        SELECT
            d.device_type,
            ROUND(SUM(eu.energy_kwh), 2) AS kwh
        FROM Energy_Usage eu
        JOIN Devices d ON d.device_id = eu.device_id
        WHERE DATE(eu.timestamp) = CURDATE()
        GROUP BY d.device_type
        ORDER BY kwh DESC
    """)
    return {
        "labels": [r["device_type"] for r in rows],
        "data":   [float(r["kwh"]) for r in rows],
    }


@router.get("/bar-chart")
def bar_chart(db=Depends(get_db), _=Depends(get_current_user)):
    """
    Floor-wise energy comparison bar chart.
    """
    rows = fetchall(db, """
        SELECT
            CONCAT(b.name, ' – Floor ', f.floor_number) AS label,
            ROUND(SUM(eu.energy_kwh), 2) AS kwh
        FROM Energy_Usage eu
        JOIN Devices d  ON d.device_id = eu.device_id
        JOIN Rooms r    ON r.room_id   = d.room_id
        JOIN Floors f   ON f.floor_id  = r.floor_id
        JOIN Buildings b ON b.building_id = f.building_id
        WHERE DATE(eu.timestamp) = CURDATE()
        GROUP BY b.building_id, f.floor_id
        ORDER BY kwh DESC
        LIMIT 8
    """)
    return {
        "labels": [r["label"] for r in rows],
        "data":   [float(r["kwh"]) for r in rows],
    }


@router.get("/efficiency")
def efficiency(db=Depends(get_db), _=Depends(get_current_user)):
    """
    Per-building efficiency % progress bars.
    """
    rows = fetchall(db, """
        SELECT
            b.name,
            COALESCE(er.efficiency_pct, 0) AS efficiency_pct,
            COALESCE(er.renewable_pct,  0) AS renewable_pct
        FROM Buildings b
        LEFT JOIN Energy_Reports er
            ON er.building_id = b.building_id
           AND er.report_date = CURDATE()
        ORDER BY b.name
    """)
    return [
        {
            "building": r["name"],
            "efficiency_pct": float(r["efficiency_pct"]),
            "renewable_pct":  float(r["renewable_pct"]),
        }
        for r in rows
    ]


@router.get("/trend")
def trend(months: int = Query(6, ge=1, le=12), db=Depends(get_db), _=Depends(get_current_user)):
    """
    6-month energy trend for reports page charts.
    """
    rows = fetchall(db, """
        SELECT
            DATE_FORMAT(report_date, '%b %Y') AS month,
            ROUND(SUM(total_kwh), 2)          AS kwh,
            ROUND(SUM(total_cost_inr), 2)     AS cost_inr,
            ROUND(SUM(carbon_kg), 2)          AS carbon_kg
        FROM Energy_Reports
        WHERE report_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        GROUP BY DATE_FORMAT(report_date, '%Y-%m')
        ORDER BY MIN(report_date)
    """, (months,))

    return {
        "labels":   [r["month"] for r in rows],
        "kwh":      [float(r["kwh"] or 0) for r in rows],
        "cost_inr": [float(r["cost_inr"] or 0) for r in rows],
        "carbon":   [float(r["carbon_kg"] or 0) for r in rows],
    }


@router.get("/top-consumers")
def top_consumers(
    limit: int = Query(5, ge=1, le=20),
    db=Depends(get_db),
    _=Depends(get_current_user)
):
    rows = fetchall(db, """
        SELECT
            d.device_name,
            d.device_type,
            ROUND(SUM(eu.energy_kwh), 3) AS kwh
        FROM Energy_Usage eu
        JOIN Devices d
            ON d.device_id = eu.device_id
        GROUP BY d.device_id, d.device_name, d.device_type
        ORDER BY kwh DESC
        LIMIT %s
    """, (limit,))

    return {
        "labels": [r["device_name"] for r in rows],
        "data": [float(r["kwh"]) for r in rows],
        "types": [r["device_type"] for r in rows],
    }

@router.get("/sdg")
def sdg_stats(db=Depends(get_db), _=Depends(get_current_user)):
    """
    SDG card stats for the Reports page.
    """
    carbon = fetchone(db, """
        SELECT COALESCE(ROUND(SUM(carbon_kg), 0), 0) AS total_kg
        FROM Energy_Reports
    """) or {"total_kg": 0}
    renewable = fetchone(db, """
        SELECT COALESCE(ROUND(AVG(renewable_pct), 1), 0) AS avg_pct
        FROM Energy_Reports WHERE report_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """) or {"avg_pct": 0}
    waste_reduction = fetchone(db, """
        SELECT COALESCE(ROUND(100 - AVG(efficiency_pct), 1), 18) AS wasted_pct
        FROM Energy_Reports WHERE report_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """) or {"wasted_pct": 18}

    carbon_saved_tons = round(float(carbon["total_kg"]) / 1000, 1)

    return {
        "sdg7":  {"label": "Renewable Share",     "value": f"+{renewable['avg_pct']}% Renewable"},
        "sdg11": {"label": "Smart Grid",           "value": "Smart Grid Integrated"},
        "sdg12": {"label": "Waste Reduction",      "value": f"-{waste_reduction['wasted_pct']}% Wasted Energy"},
        "sdg13": {"label": "Carbon Saved",         "value": f"{carbon_saved_tons} Tons CO2 Saved"},
    }

@router.get("/energy-logs")
def energy_logs(
    period: str = Query("week"),
    limit: int = Query(25, ge=1, le=100),
    db=Depends(get_db),
    _=Depends(get_current_user)
):
    if period == "week":
        interval = "7 DAY"
    elif period == "month":
        interval = "30 DAY"
    elif period == "year":
        interval = "365 DAY"
    else:
        interval = "7 DAY"

    rows = fetchall(db, f"""
        SELECT
            eu.usage_id,
            d.device_name,
            d.device_type,
            ROUND(eu.energy_kwh, 3) AS energy_kwh,
            ROUND(eu.power_kw, 3) AS power_kw,
            ROUND(eu.cost_inr, 2) AS cost_inr,
            eu.timestamp
        FROM Energy_Usage eu
        JOIN Devices d
            ON d.device_id = eu.device_id
        WHERE eu.timestamp >= DATE_SUB(
            NOW(),
            INTERVAL {interval}
        )
        ORDER BY eu.timestamp DESC
        LIMIT %s
    """, (limit,))

    return {
        "period": period,
        "count": len(rows),
        "logs": rows
    }