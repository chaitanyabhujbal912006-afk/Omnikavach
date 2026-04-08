from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


AUTH_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "auth.db"
JWT_SECRET = os.getenv("OMNIKAVACH_JWT_SECRET", "omnikavach-dev-jwt-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 12 * 60
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthUser(BaseModel):
    id: int
    email: str
    name: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


def _get_auth_conn() -> sqlite3.Connection:
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        120000,
    ).hex()
    return salt, password_hash


def _verify_password(password: str, salt: str, password_hash: str) -> bool:
    _, candidate_hash = _hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def init_auth_db() -> None:
    conn = _get_auth_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'doctor')),
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    existing = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    if existing == 0:
        seeded_users = [
            ("admin@omnikavach.local", "Dr. Asha Mehta", "admin", "Admin@123"),
            ("doctor@omnikavach.local", "Dr. Rohan Iyer", "doctor", "Doctor@123"),
        ]
        for email, name, role, password in seeded_users:
            salt, password_hash = _hash_password(password)
            conn.execute(
                """
                INSERT INTO users (email, name, role, password_salt, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    name,
                    role,
                    salt,
                    password_hash,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()

    conn.close()


def _user_from_row(row: sqlite3.Row) -> AuthUser:
    return AuthUser(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
    )


def authenticate_user(email: str, password: str) -> Optional[AuthUser]:
    conn = _get_auth_conn()
    row = conn.execute(
        "SELECT id, email, name, role, password_salt, password_hash FROM users WHERE lower(email) = lower(?)",
        (email,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    if not _verify_password(password, row["password_salt"], row["password_hash"]):
        return None

    return _user_from_row(row)


def create_access_token(user: AuthUser) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> AuthUser:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return AuthUser(
            id=int(payload["sub"]),
            email=payload["email"],
            name=payload["name"],
            role=payload["role"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return _decode_token(credentials.credentials)


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user
