
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from core.database import get_db, fetchall, fetchone, execute
from core.auth import get_current_user, require_admin

router = APIRouter(tags=["Buildings & Rooms"])


# ── Pydantic models ─────────────────────────────────────────────

class BuildingIn(BaseModel):
    name: str
    city: str
    address: Optional[str] = None
    building_type: Optional[str] = None
    total_floors: int = 1
    construction_year: Optional[int] = None

class FloorIn(BaseModel):
    floor_number: int
    label: Optional[str] = None

class RoomIn(BaseModel):
    room_number: str
    room_type: Optional[str] = None
    area_sqft: Optional[float] = None
    occupancy_status: str = "vacant"

class RoomPatch(BaseModel):
    room_type: Optional[str] = None
    area_sqft: Optional[float] = None
    occupancy_status: Optional[str] = None


# ═══════════════════════════════════════════
# BUILDINGS
# ═══════════════════════════════════════════

@router.get("/buildings")
def list_buildings(db=Depends(get_db), _=Depends(get_current_user)):
    return fetchall(db, "SELECT * FROM Buildings ORDER BY name")


@router.post("/buildings", status_code=201)
def create_building(body: BuildingIn, db=Depends(get_db), _=Depends(require_admin)):
    bid = execute(db,
        "INSERT INTO Buildings (name,city,address,building_type,total_floors,construction_year) VALUES (%s,%s,%s,%s,%s,%s)",
        (body.name, body.city, body.address, body.building_type, body.total_floors, body.construction_year))
    return fetchone(db, "SELECT * FROM Buildings WHERE building_id=%s", (bid,))


@router.get("/buildings/{building_id}")
def get_building(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    b = fetchone(db, "SELECT * FROM Buildings WHERE building_id=%s", (building_id,))
    if not b:
        raise HTTPException(404, "Building not found")
    return b


@router.patch("/buildings/{building_id}")
def update_building(building_id: int, body: BuildingIn, db=Depends(get_db), _=Depends(require_admin)):
    _need_building(db, building_id)
    execute(db,
        "UPDATE Buildings SET name=%s,city=%s,address=%s,building_type=%s,total_floors=%s WHERE building_id=%s",
        (body.name, body.city, body.address, body.building_type, body.total_floors, building_id))
    return fetchone(db, "SELECT * FROM Buildings WHERE building_id=%s", (building_id,))


@router.delete("/buildings/{building_id}", status_code=204)
def delete_building(building_id: int, db=Depends(get_db), _=Depends(require_admin)):
    _need_building(db, building_id)
    execute(db, "DELETE FROM Buildings WHERE building_id=%s", (building_id,))


@router.get("/buildings/{building_id}/tree")
def building_tree(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """
    Returns the full nested tree used to build the facility sidebar:
    { building, floors: [{ floor, rooms: [{ room, device_count, today_kwh }] }] }
    """
    building = fetchone(db, "SELECT * FROM Buildings WHERE building_id=%s", (building_id,))
    if not building:
        raise HTTPException(404, "Building not found")

    floors = fetchall(db,
        "SELECT * FROM Floors WHERE building_id=%s ORDER BY floor_number", (building_id,))

    for floor in floors:
        rooms = fetchall(db, """
            SELECT
                r.*,
                COUNT(d.device_id)                        AS device_count,
                COALESCE(ROUND(SUM(eu.energy_kwh),2), 0)  AS today_kwh
            FROM Rooms r
            LEFT JOIN Devices d ON d.room_id = r.room_id
            LEFT JOIN Energy_Usage eu
                   ON eu.device_id = d.device_id
                  AND DATE(eu.timestamp) = CURDATE()
            WHERE r.floor_id = %s
            GROUP BY r.room_id
            ORDER BY r.room_number
        """, (floor["floor_id"],))
        floor["rooms"] = rooms

    building["floors"] = floors
    return building


# ═══════════════════════════════════════════
# FLOORS
# ═══════════════════════════════════════════

@router.get("/buildings/{building_id}/floors")
def list_floors(building_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    _need_building(db, building_id)
    return fetchall(db,
        "SELECT * FROM Floors WHERE building_id=%s ORDER BY floor_number", (building_id,))


@router.post("/buildings/{building_id}/floors", status_code=201)
def create_floor(building_id: int, body: FloorIn, db=Depends(get_db), _=Depends(require_admin)):
    _need_building(db, building_id)
    dup = fetchone(db,
        "SELECT floor_id FROM Floors WHERE building_id=%s AND floor_number=%s",
        (building_id, body.floor_number))
    if dup:
        raise HTTPException(409, "Floor number already exists in this building")
    fid = execute(db,
        "INSERT INTO Floors (building_id,floor_number,label) VALUES (%s,%s,%s)",
        (building_id, body.floor_number, body.label))
    return fetchone(db, "SELECT * FROM Floors WHERE floor_id=%s", (fid,))


@router.delete("/floors/{floor_id}", status_code=204)
def delete_floor(floor_id: int, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT floor_id FROM Floors WHERE floor_id=%s", (floor_id,)):
        raise HTTPException(404, "Floor not found")
    execute(db, "DELETE FROM Floors WHERE floor_id=%s", (floor_id,))


# ═══════════════════════════════════════════
# ROOMS
# ═══════════════════════════════════════════

@router.get("/floors/{floor_id}/rooms")
def list_rooms(floor_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    return fetchall(db,
        "SELECT * FROM Rooms WHERE floor_id=%s ORDER BY room_number", (floor_id,))


@router.post("/floors/{floor_id}/rooms", status_code=201)
def create_room(floor_id: int, body: RoomIn, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT floor_id FROM Floors WHERE floor_id=%s", (floor_id,)):
        raise HTTPException(404, "Floor not found")
    rid = execute(db,
        "INSERT INTO Rooms (floor_id,room_number,room_type,area_sqft,occupancy_status) VALUES (%s,%s,%s,%s,%s)",
        (floor_id, body.room_number, body.room_type, body.area_sqft, body.occupancy_status))
    return fetchone(db, "SELECT * FROM Rooms WHERE room_id=%s", (rid,))


@router.get("/rooms/{room_id}")
def get_room(room_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Room detail card: info + today's energy + device count."""
    room = fetchone(db, """
        SELECT
            r.*,
            f.floor_number,
            b.name AS building_name,
            COUNT(d.device_id)                        AS device_count,
            COALESCE(ROUND(SUM(eu.energy_kwh), 2), 0) AS today_kwh
        FROM Rooms r
        JOIN Floors f    ON f.floor_id    = r.floor_id
        JOIN Buildings b ON b.building_id = f.building_id
        LEFT JOIN Devices d    ON d.room_id = r.room_id
        LEFT JOIN Energy_Usage eu ON eu.device_id = d.device_id AND DATE(eu.timestamp) = CURDATE()
        WHERE r.room_id = %s
        GROUP BY r.room_id
    """, (room_id,))
    if not room:
        raise HTTPException(404, "Room not found")
    return room


@router.patch("/rooms/{room_id}")
def update_room(room_id: int, body: RoomPatch, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT room_id FROM Rooms WHERE room_id=%s", (room_id,)):
        raise HTTPException(404, "Room not found")
    updates = body.model_dump(exclude_none=True)
    if updates:
        clauses = ", ".join(f"{k}=%s" for k in updates)
        execute(db, f"UPDATE Rooms SET {clauses} WHERE room_id=%s",
                (*updates.values(), room_id))
    return fetchone(db, "SELECT * FROM Rooms WHERE room_id=%s", (room_id,))


@router.delete("/rooms/{room_id}", status_code=204)
def delete_room(room_id: int, db=Depends(get_db), _=Depends(require_admin)):
    if not fetchone(db, "SELECT room_id FROM Rooms WHERE room_id=%s", (room_id,)):
        raise HTTPException(404, "Room not found")
    execute(db, "DELETE FROM Rooms WHERE room_id=%s", (room_id,))


# ── helpers ─────────────────────────────────────────────────────

def _need_building(db, building_id: int):
    if not fetchone(db, "SELECT building_id FROM Buildings WHERE building_id=%s", (building_id,)):
        raise HTTPException(404, "Building not found")