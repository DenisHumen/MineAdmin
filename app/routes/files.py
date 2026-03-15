import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Server
from app.routes.auth import get_current_user
from app.file_manager import (
    list_directory, read_text_file, save_text_file,
    delete_path, create_directory, rename_path,
    get_directory_size,
)
from app.system_monitor import format_bytes

router = APIRouter(prefix="/api/servers/{server_id}/files", tags=["files"])
logger = logging.getLogger("mineadmin.routes.files")


async def _get_server_dir(server_id: int, session: AsyncSession) -> Path:
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return Path(server.server_dir)


@router.get("")
async def list_files(server_id: int, path: str = "",
                     session: AsyncSession = Depends(get_session),
                     user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    try:
        items = list_directory(server_dir, path)
        return {"path": path, "items": items}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/read")
async def read_file(server_id: int, path: str,
                    session: AsyncSession = Depends(get_session),
                    user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    try:
        return read_text_file(server_dir, path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (PermissionError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/save")
async def save_file(server_id: int, request: Request,
                    session: AsyncSession = Depends(get_session),
                    user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    data = await request.json()
    path = data.get("path", "")
    content = data.get("content", "")
    try:
        save_text_file(server_dir, path, content)
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/upload")
async def upload_file(server_id: int,
                      path: str = Form(""),
                      file: UploadFile = File(...),
                      session: AsyncSession = Depends(get_session),
                      user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    target_dir = (server_dir / path).resolve()

    if not str(target_dir).startswith(str(server_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file.filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    stat = file_path.stat()
    return {
        "success": True,
        "name": file.filename,
        "size": format_bytes(stat.st_size),
        "path": str(file_path.relative_to(server_dir)),
    }


@router.get("/download")
async def download_file(server_id: int, path: str, token: str = "",
                        session: AsyncSession = Depends(get_session)):
    from app.routes.auth import decode_token
    if token:
        decode_token(token)
    else:
        raise HTTPException(status_code=401, detail="Token required")
    server_dir = await _get_server_dir(server_id, session)
    file_path = (server_dir / path).resolve()

    if not str(file_path).startswith(str(server_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.delete("")
async def delete(server_id: int, path: str,
                 session: AsyncSession = Depends(get_session),
                 user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    try:
        delete_path(server_dir, path)
        return {"success": True}
    except (FileNotFoundError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mkdir")
async def mkdir(server_id: int, request: Request,
                session: AsyncSession = Depends(get_session),
                user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    data = await request.json()
    path = data.get("path", "")
    try:
        create_directory(server_dir, path)
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/rename")
async def rename(server_id: int, request: Request,
                 session: AsyncSession = Depends(get_session),
                 user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    data = await request.json()
    path = data.get("path", "")
    new_name = data.get("new_name", "")
    try:
        rename_path(server_dir, path, new_name)
        return {"success": True}
    except (FileNotFoundError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/size")
async def dir_size(server_id: int, path: str = "",
                   session: AsyncSession = Depends(get_session),
                   user: dict = Depends(get_current_user)):
    server_dir = await _get_server_dir(server_id, session)
    target = (server_dir / path).resolve()
    if not str(target).startswith(str(server_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    size = get_directory_size(target)
    return {"size": format_bytes(size)}
