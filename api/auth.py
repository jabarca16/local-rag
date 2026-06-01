import os
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

bearer = HTTPBearer()


def _cfg(key: str, default: str) -> str:
    return os.getenv(key, default)


def verificar_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hashear_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def crear_token(data: dict) -> str:
    payload = data.copy()
    exp = datetime.now(timezone.utc) + timedelta(minutes=int(_cfg("JWT_EXPIRE_MINUTES", "480")))
    payload.update({"exp": exp})
    return jwt.encode(payload, _cfg("JWT_SECRET", "dev-secret"), algorithm=_cfg("JWT_ALGORITHM", "HS256"))


def validar_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            _cfg("JWT_SECRET", "dev-secret"),
            algorithms=[_cfg("JWT_ALGORITHM", "HS256")],
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")


def validar_token_o_service_key(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    """Acepta un JWT válido O el SERVICE_API_KEY — para endpoints accedidos por servicios internos."""
    service_key = _cfg("SERVICE_API_KEY", "")
    token = credentials.credentials

    if service_key and token == service_key:
        return {"sub": "service", "role": "service"}

    try:
        payload = jwt.decode(token, _cfg("JWT_SECRET", "dev-secret"), algorithms=[_cfg("JWT_ALGORITHM", "HS256")])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
