from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db as _get_db
from app.middleware.auth import require_auth as _require_auth

get_db = _get_db
require_auth = _require_auth
