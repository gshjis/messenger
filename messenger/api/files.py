"""Роутеры для загрузки и скачивания файлов."""

import os
from pathlib import Path

import magic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.api.auth import get_current_user
from messenger.config import settings
from messenger.database import get_session
from messenger.models.chat import Chat
from messenger.models.chat_member import ChatMember
from messenger.models.message import Message
from messenger.models.user import User

router = APIRouter(prefix="/api/files", tags=["files"])


async def check_chat_access(
    chat_id: int,
    user_id: int,
    session: AsyncSession,
) -> bool:
    """Проверка доступа к чату."""
    result = await session.exec(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
        )
    )
    return result.first() is not None


@router.post("/{chat_id}/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    chat_id: int,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Загрузка файла в чат."""
    assert current_user.id is not None

    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, current_user.id, session)
    if not has_access:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Проверка размера
    content = await file.read()
    file_size = len(content)
    max_size = settings.max_file_size_mb * 1024 * 1024

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max: {settings.max_file_size_mb}MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Проверка MIME типа через python-magic
    mime = magic.Magic(mime=True)
    file_mime = mime.from_buffer(content)

    if file_mime not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_mime}' is not allowed",
        )

    # Сохранение файла
    upload_dir = Path(settings.upload_dir) / str(chat_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Безопасное имя файла
    original_name = file.filename or "unnamed"
    safe_name = original_name.replace(" ", "_").replace("/", "_")
    file_path = upload_dir / safe_name

    # Уникальное имя (добавляем ID пользователя)
    counter = 0
    while file_path.exists():
        counter += 1
        name_parts = safe_name.rsplit(".", 1)
        if len(name_parts) == 2:
            file_path = upload_dir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
        else:
            file_path = upload_dir / f"{safe_name}_{counter}"

    file_path.write_bytes(content)

    # Создание сообщения с файлом
    message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=file.file.name if file.file else None,
        file_path=str(file_path.relative_to(Path(settings.upload_dir).parent)),
        file_mime=file_mime,
        file_size=file_size,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    logger.info(f"File uploaded: {safe_name} ({file_mime}, {file_size} bytes) by user {current_user.id}")

    return {
        "message_id": message.id,
        "file_path": message.file_path,
        "file_mime": file_mime,
        "file_size": file_size,
    }


@router.get("/{chat_id}/{file_path:path}")
async def download_file(
    chat_id: int,
    file_path: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Скачивание файла с проверкой прав."""
    assert current_user.id is not None

    # Проверка доступа к чату
    has_access = await check_chat_access(chat_id, current_user.id, session)
    if not has_access:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Проверка что файл существует
    full_path = Path(settings.upload_dir) / file_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Проверка что файл принадлежит этому чату
    if str(chat_id) not in str(full_path):
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=str(full_path),
        filename=full_path.name,
        media_type="application/octet-stream",
    )
