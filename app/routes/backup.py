import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Server
from app.routes.auth import get_current_user
from app.config import load_config, get_backup_dir
from app.backup_manager import (
    create_backup, get_backup_progress, list_backups,
    delete_backup, cleanup_old_backups,
)

router = APIRouter(prefix="/api/backups", tags=["backups"])
logger = logging.getLogger("mineadmin.routes.backup")


@router.post("/{server_id}")
async def backup_server(server_id: int,
                        request: Request,
                        background_tasks: BackgroundTasks,
                        session: AsyncSession = Depends(get_session),
                        user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}

    cfg = load_config()
    backup_cfg = cfg.get("backup", {})

    backup_path = data.get("backup_path") or backup_cfg.get("path") or str(get_backup_dir())
    use_sftp = data.get("use_sftp", False)
    sftp_config = None
    if use_sftp:
        sftp_config = backup_cfg.get("sftp", {})
        if data.get("sftp"):
            sftp_config.update(data["sftp"])
        sftp_config["enabled"] = True

    task_id = f"backup_{server_id}_{__import__('time').time_ns()}"

    server_info = {
        "jar_file": server.jar_file,
        "java_path": server.java_path,
        "memory_min": server.memory_min,
        "memory_max": server.memory_max,
        "port": server.port,
        "jvm_args": server.jvm_args or "",
        "mc_version": server.mc_version,
    }

    async def do_backup():
        result = await create_backup(
            server.id, server.name, server.server_dir,
            task_id, backup_path, sftp_config, server_info,
        )
        schedule_cfg = backup_cfg.get("schedule", {})
        if schedule_cfg.get("enabled") and schedule_cfg.get("max_backups"):
            cleanup_old_backups(server.id, schedule_cfg["max_backups"])

    background_tasks.add_task(do_backup)
    return {"task_id": task_id, "status": "started"}


@router.get("/progress/{task_id}")
async def backup_progress(task_id: str, user: dict = Depends(get_current_user)):
    return get_backup_progress(task_id)


@router.get("")
async def get_backups(server_id: int = None, user: dict = Depends(get_current_user)):
    backups = list_backups(server_id)
    return {"backups": backups}


@router.delete("/{filename:path}")
async def remove_backup(filename: str, user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    if delete_backup(filename):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Backup not found")


@router.get("/download/{filename:path}")
async def download_backup(filename: str, user: dict = Depends(get_current_user)):
    backup_dir = get_backup_dir()
    path = backup_dir / filename
    if not path.exists() or path.parent != backup_dir:
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, filename=filename, media_type="application/zip")
