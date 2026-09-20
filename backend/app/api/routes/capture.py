from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.capture import (
    CaptureRequest,
    CaptureResponse,
)
from app.services.capture_service import CaptureService


router = APIRouter(
    prefix="/api/v1",
    tags=["capture"],
)


@router.post(
    "/capture",
    response_model=CaptureResponse,
)
async def capture(
    payload: CaptureRequest,
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:

    service = CaptureService(db)

    result = await service.capture(payload)

    return CaptureResponse(
        resource_id=result.resource_id,
        snapshot_id=result.snapshot_id,
        activity_id=result.activity_id,
        duplicate=result.duplicate,
    )