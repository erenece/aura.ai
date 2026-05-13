import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from app.core.config import settings
from app.db.database import get_session
from app.db import models


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), 260000)
    return f"pbkdf2:sha256:260000:{salt}:{key.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _, algorithm, iterations, salt, key_hex = hashed.split(":", 4)
        key = hashlib.pbkdf2_hmac(algorithm, plain.encode("utf-8"), salt.encode(), int(iterations))
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def create_token(user_id: int, email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "email": email, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


class AuthService:
    def register(self, email: str, name: str, password: str, role: str = "owner") -> dict:
        db = get_session()
        try:
            existing = db.query(models.User).filter(models.User.email == email).first()
            if existing:
                return {"error": "Bu e-posta adresi zaten kayıtlı"}
            user = models.User(
                email=email,
                name=name,
                hashed_password=hash_password(password),
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            token = create_token(user.id, user.email, user.role)
            return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}
        finally:
            db.close()

    def login(self, email: str, password: str) -> dict:
        db = get_session()
        try:
            user = db.query(models.User).filter(models.User.email == email).first()
            if not user or not verify_password(password, user.hashed_password):
                return {"error": "E-posta veya şifre hatalı"}
            if not user.is_active:
                return {"error": "Hesabınız devre dışı"}
            token = create_token(user.id, user.email, user.role)
            return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}
        finally:
            db.close()

    def get_user_from_token(self, token: str) -> Optional[dict]:
        payload = decode_token(token)
        if not payload:
            return None
        db = get_session()
        try:
            user = db.get(models.User, int(payload["sub"]))
            if not user or not user.is_active:
                return None
            return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}
        finally:
            db.close()

    def list_users(self) -> list:
        db = get_session()
        try:
            users = db.query(models.User).all()
            return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
                     "is_active": u.is_active, "created_at": u.created_at.isoformat()} for u in users]
        finally:
            db.close()
