from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth_service import AuthService

router = APIRouter()
service = AuthService()


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str = "owner"


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(data: RegisterRequest):
    result = service.register(data.email, data.name, data.password, data.role)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/login")
def login(data: LoginRequest):
    result = service.login(data.email, data.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@router.get("/me")
def get_me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token gerekli")
    token = authorization.split(" ", 1)[1]
    user = service.get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token")
    return user


@router.get("/users")
def list_users():
    return service.list_users()
