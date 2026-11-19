from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import User, Role
from app.dependencies import require_admin
from app.services.auth_service import hash_password
from app.templates import render_template

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_class=HTMLResponse)
def users_list_view(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    users = db.query(User).order_by(desc(User.created_at)).all()
    roles = db.query(Role).all()

    return render_template(
        request,
        "users/index.html",
        {
            "current_user": admin_user,
            "active_page": "users",
            "users": users,
            "roles": roles,
        },
    )


@router.post("/create")
def user_create_post(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role_code: str = Form("STAFF"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    user = User(
        full_name=full_name.strip(),
        username=username.strip().lower(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role_code=role_code,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return RedirectResponse(url="/users", status_code=302)
