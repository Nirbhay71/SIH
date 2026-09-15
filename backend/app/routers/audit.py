from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.hashchain import compute_hash
from app.models import VerificationRecord

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/verify-chain")
async def verify_chain(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VerificationRecord)
        .where(VerificationRecord.record_hash.is_not(None))
        .order_by(VerificationRecord.decided_at.asc())
    )
    records = result.scalars().all()

    prev_hash = ""
    for record in records:
        from app.routers.verification import _serialize

        expected_hash = compute_hash(_serialize(record), prev_hash)
        if record.prev_hash != prev_hash or record.record_hash != expected_hash:
            return {"valid": False, "first_broken_record_id": record.id, "checked": len(records)}
        prev_hash = record.record_hash

    return {"valid": True, "first_broken_record_id": None, "checked": len(records)}
