from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import bcrypt
from sqlalchemy.orm import Session
from app.config import settings
from app.models import User, AuditLog
from app.models.base import get_utc_now


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def record_user_login(db: Session, user: User, ip_address: Optional[str] = None):
    user.last_login_at = get_utc_now()
    log = AuditLog(
        user_id=user.id,
        action="LOGIN",
        entity_name="User",
        entity_id=user.id,
        new_values={"username": user.username, "login_at": user.last_login_at.isoformat()},
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()
