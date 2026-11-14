"""Autenticación JWT para la demo. Usuarios y roles se definen en .env (APP_USERS); nunca en el código."""
from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from common import config

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _users() -> dict[str, tuple[str, str]]:
    out = {}
    for item in (config.APP_USERS or "").split(","):
        parts = item.strip().split(":")
        if len(parts) == 3:
            out[parts[0]] = (parts[1], parts[2])
    return out


def authenticate(username: str, password: str) -> dict | None:
    user = _users().get(username)
    if not user or not hmac.compare_digest(user[0].encode(), (password or "").encode()):
        return None
    return {"username": username, "role": user[1]}


def create_token(user: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user["username"], "role": user["role"], "exp": exp}, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        data = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return {"username": data["sub"], "role": data["role"]}
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado",
                            headers={"WWW-Authenticate": "Bearer"}) from exc


def current_user(token: str = Depends(oauth2)) -> dict:
    return decode_token(token)


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere rol admin")
    return user


class RateLimiter:
    """Límite simple en memoria: N solicitudes por minuto por usuario."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiadas consultas al asistente; espere un minuto")
        q.append(now)
