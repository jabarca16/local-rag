import os
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from api.auth import crear_token

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    usuario = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    if body.username != usuario or body.password != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    token = crear_token({"sub": body.username})
    return {"access_token": token, "token_type": "bearer"}
