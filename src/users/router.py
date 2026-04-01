from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.dependencies import get_db
from src.core.security.dependencies import get_current_user
from . import models, schemas, service

router = APIRouter(prefix="/users", tags=["users"])

MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024


@router.get("/me/profile", response_model=schemas.UserProfileRead)
async def get_my_profile(current_user: models.User = Depends(get_current_user)):
    return service.serialize_profile(current_user)


@router.patch("/me/profile", response_model=schemas.UserProfileRead)
async def patch_my_profile(
    payload: schemas.UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    updated_user = await service.update_bio(db, current_user, payload.bio)
    return service.serialize_profile(updated_user)


@router.put("/me/avatar", response_model=schemas.AvatarUploadResponse)
async def put_my_avatar(
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    mime_type = (avatar.content_type or "").lower()
    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image/* avatars are allowed")

    content = await avatar.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar file is empty")

    if len(content) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar exceeds 5 MB limit")

    updated_user = await service.save_avatar(db, current_user, content, mime_type)
    return schemas.AvatarUploadResponse(
        has_avatar=True,
        avatar_url=service.build_avatar_url(updated_user.id),
        avatar_mime_type=updated_user.avatar_mime_type,
    )


@router.delete("/me/avatar", response_model=schemas.AvatarUploadResponse)
async def delete_my_avatar(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    await service.remove_avatar(db, current_user)
    return schemas.AvatarUploadResponse(has_avatar=False, avatar_url=None, avatar_mime_type=None)


@router.get("/me/last-seen", response_model=schemas.UserLastSeenRead)
async def get_my_last_seen(current_user: models.User = Depends(get_current_user)):
    return schemas.UserLastSeenRead(user_id=current_user.id, last_seen_at=current_user.last_seen_at)


@router.patch("/me/last-seen", response_model=schemas.UserLastSeenRead)
async def patch_my_last_seen(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    last_seen_at = await service.update_last_seen(db, current_user, force=True)
    return schemas.UserLastSeenRead(user_id=current_user.id, last_seen_at=last_seen_at)


@router.get("/{user_id}/profile", response_model=schemas.UserProfileRead)
async def get_user_profile(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return service.serialize_profile(user)


@router.get("/{user_id}/last-seen", response_model=schemas.UserLastSeenRead)
async def get_user_last_seen(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return schemas.UserLastSeenRead(user_id=user.id, last_seen_at=user.last_seen_at)


@router.get("/{user_id}/avatar")
async def get_user_avatar(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_id(db, user_id)
    if not user or not user.avatar or not user.avatar_mime_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    return Response(content=user.avatar, media_type=user.avatar_mime_type)
