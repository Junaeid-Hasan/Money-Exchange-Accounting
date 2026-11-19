from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import decode_access_token


def get_token_from_request(request: Request) -> Optional[str]:
    # Check Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    
    # Check Cookie next
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if cookie_token.startswith("Bearer "):
            return cookie_token.split(" ")[1]
        return cookie_token
        
    return None


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = get_token_from_request(request)
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    username: str = payload.get("sub")
    if not username:
        return None
    
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if not user:
        # Check if browser HTML request vs JSON API
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/login?next=" + request.url.path}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role_code != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required for this operation"
        )
    return current_user


def require_accountant_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role_code not in ["ADMIN", "ACCOUNTANT"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accountant or Administrator privileges required"
        )
    return current_user
