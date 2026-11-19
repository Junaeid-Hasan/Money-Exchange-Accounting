from fastapi import APIRouter, Depends, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import authenticate_user, create_access_token, record_user_login
from app.templates import render_template

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render_template(request, "auth/login.html", {"error": None})


@router.post("/login")
def login_post(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    next: str = "/dashboard",
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username=username, password=password)
    if not user:
        return render_template(
            request,
            "auth/login.html",
            {"error": "Invalid username or password. Please try again."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Record login
    client_ip = request.client.host if request.client else None
    record_user_login(db, user, ip_address=client_ip)

    # Generate token
    token = create_access_token(data={"sub": user.username, "role": user.role_code})

    redirect_url = next if next and next.startswith("/") else "/dashboard"
    redirect = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=60 * 60 * 8,  # 8 hours
        samesite="lax",
    )
    return redirect


@router.get("/logout")
def logout(response: Response):
    redirect = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    redirect.delete_cookie("access_token")
    return redirect
