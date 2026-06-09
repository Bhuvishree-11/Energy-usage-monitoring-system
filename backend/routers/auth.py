from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional

from core.database import get_db, fetchone, execute
from core.auth import verify_password, hash_password, create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    name:         str
    role:         str
    avatar_url:   Optional[str]

class PasswordChange(BaseModel):
    current_password: str
    new_password:     str

class RegisterIn(BaseModel):
    name:     str
    email:    str
    password: str
    role:     str = "viewer"


@router.post("/login", response_model=LoginOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    user = fetchone(db, "SELECT * FROM Users WHERE email = %s", (form.username,))
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    token = create_token({
        "sub":   str(user["user_id"]),
        "email": user["email"],
        "name":  user["name"],
        "role":  user["role"],
    })
    return {
        "access_token": token,
        "user_id":      user["user_id"],
        "name":         user["name"],
        "role":         user["role"],
        "avatar_url":   user.get("avatar_url"),
    }


@router.get("/me")
def me(payload: dict = Depends(get_current_user), db=Depends(get_db)):
    user = fetchone(db, """
        SELECT user_id, name, email, role, avatar_url, created_at
        FROM Users WHERE user_id = %s
    """, (int(payload["sub"]),))
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.post("/change-password")
def change_password(
    body: PasswordChange,
    payload: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    user = fetchone(db, "SELECT * FROM Users WHERE user_id = %s", (int(payload["sub"]),))
    if not user or not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(401, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    execute(db,
        "UPDATE Users SET password_hash = %s WHERE user_id = %s",
        (hash_password(body.new_password), user["user_id"])
    )
    return {"message": "Password updated"}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db=Depends(get_db)):
    if body.role not in ("admin", "manager", "viewer"):
        raise HTTPException(400, "Invalid role. Must be admin, manager or viewer")

    existing = fetchone(db, "SELECT user_id FROM Users WHERE email = %s", (body.email,))
    if existing:
        raise HTTPException(400, "Email already registered")

    uid = execute(db,
        "INSERT INTO Users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        (body.name, body.email, hash_password(body.password), body.role)
    )
    return {"user_id": uid, "name": body.name, "email": body.email, "role": body.role}