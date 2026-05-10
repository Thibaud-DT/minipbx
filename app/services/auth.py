from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdminUser
from app.security import hash_password, verify_password


SESSION_ADMIN_ID = "admin_user_id"


def has_admin(db: Session) -> bool:
    return db.scalar(select(AdminUser.id).limit(1)) is not None


def create_admin(db: Session, username: str, password: str, *, commit: bool = True) -> AdminUser:
    admin = AdminUser(username=username.strip(), password_hash=hash_password(password))
    db.add(admin)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(admin)
    return admin


def authenticate_admin(db: Session, username: str, password: str) -> AdminUser | None:
    admin = db.scalar(select(AdminUser).where(AdminUser.username == username.strip()))
    if not admin or not verify_password(password, admin.password_hash):
        return None
    return admin


def login(request: Request, admin: AdminUser) -> None:
    request.session[SESSION_ADMIN_ID] = admin.id


def logout(request: Request) -> None:
    request.session.pop(SESSION_ADMIN_ID, None)


def current_admin(request: Request, db: Session) -> AdminUser | None:
    admin_id = request.session.get(SESSION_ADMIN_ID)
    if not admin_id:
        return None
    return db.get(AdminUser, admin_id)
