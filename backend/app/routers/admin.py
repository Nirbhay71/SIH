"""Admin watchlist CRUD (Part D.2 / F.5). Auth is a single hardcoded demo
login via HTTP Basic — intentionally minimal per Part J (no production-grade
auth for a 1-day build)."""
import secrets

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, STORAGE_DIR
from app.database import get_db
from app.models import WatchlistFace
from app.modules.face import embed_face

router = APIRouter(prefix="/api/admin", tags=["admin"])
security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(401, "Invalid admin credentials", headers={"WWW-Authenticate": "Basic"})
    return credentials.username


@router.post("/watchlist")
async def add_watchlist(
    reference_label: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    image_bytes = await file.read()
    photo_path = STORAGE_DIR / "watchlist" / f"{reference_label.replace(' ', '_')}_{file.filename}"
    photo_path.write_bytes(image_bytes)

    entry = WatchlistFace(
        reference_label=reference_label,
        embedding=embed_face(image_bytes),
        photo_path=str(photo_path),
        uploaded_by=admin,
    )
    db.add(entry)
    await db.commit()
    return {"id": entry.id, "reference_label": entry.reference_label}


@router.get("/watchlist")
async def list_watchlist(db: AsyncSession = Depends(get_db), admin: str = Depends(require_admin)):
    result = await db.execute(select(WatchlistFace))
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "reference_label": e.reference_label,
            "uploaded_at": e.uploaded_at.isoformat(),
            "uploaded_by": e.uploaded_by,
            "photo_url": f"/api/admin/watchlist/{e.id}/photo",
        }
        for e in entries
    ]


@router.get("/watchlist/{entry_id}/photo")
async def watchlist_photo(entry_id: str, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import FileResponse

    result = await db.execute(select(WatchlistFace).where(WatchlistFace.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404)
    return FileResponse(entry.photo_path)


@router.delete("/watchlist/{entry_id}")
async def delete_watchlist(entry_id: str, db: AsyncSession = Depends(get_db), admin: str = Depends(require_admin)):
    result = await db.execute(select(WatchlistFace).where(WatchlistFace.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404)
    await db.delete(entry)
    await db.commit()
    return {"deleted": True}
