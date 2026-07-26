"""Session authentication and role checks for the dashboard."""

import base64
import hashlib
import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from .database import get_session
from .models import User

router = APIRouter(tags=["authentication"])


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random, per-password salt."""
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$8$1${}${}".format(
        base64.b64encode(salt).decode("ascii"), base64.b64encode(derived).decode("ascii")
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n), r=int(r), p=int(p),
        )
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    user = getattr(request.state, "user", None)
    if user is None:
        user_id = request.session.get("user_id")
        user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="administrator role required")
    return user


@router.get("/login")
def login_page(request: Request, error: int = 0):
    from .routers.pages import templates

    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Đăng nhập", "error": bool(error)},
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(..., min_length=1, max_length=64),
    password: str = Form(..., min_length=1, max_length=256),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not verify_password(password, user.password_hash):
        return RedirectResponse("/login?error=1", status_code=303)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.post("/api/users", status_code=status.HTTP_201_CREATED)
def create_user(
    username: str = Form(..., min_length=3, max_length=64),
    password: str = Form(..., min_length=12, max_length=256),
    role: str = Form(...),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Create an operator or administrator; restricted to administrators."""
    if role not in {"admin", "operator"}:
        raise HTTPException(status_code=422, detail="role must be admin or operator")
    if session.exec(select(User).where(User.username == username)).first() is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}
