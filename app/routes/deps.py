from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser
from app.services.auth import current_admin, has_admin


def optional_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser | None:
    return current_admin(request, db)


def is_configured(db: Session = Depends(get_db)) -> bool:
    return has_admin(db)
