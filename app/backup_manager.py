import os
import shutil
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import paramiko

from app.config import load_config, get_backup_dir
from app.server_manager import stop_server, start_server, get_server_status

logger = logging.getLogger("mineadmin.backup")

_backup_progress: dict[str, dict] = {}


def get_backup_progress(task_id: str) -> dict:
    return _backup_progress.get(task_id, {"status": "unknown", "percent": 0, "message": ""})


def _set_progress(task_id: str, status: str, percent: int, message: str, **extra):
    _backup_progress[task_id] = {"status": status, "percent": percent, "message": message, **extra}


async def create_backup(server_id: int, server_name: str, server_dir: str,
                         task_id: str, backup_path: str = None,
                         sftp_config: dict = None,
                         server_info: dict = None) -> dict:
    try:
        _set_progress(task_id, "running", 5, "Подготовка бекапа...")

        if backup_path is None:
            backup_path = str(get_backup_dir())

        backup_dir = Path(backup_path)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in server_name)
        archive_name = f"{safe_name}_{server_id}_{timestamp}"
        archive_path = backup_dir / archive_name

        was_running = False
        if sftp_config and sftp_config.get("enabled"):
            status = get_server_status(server_id)
            if status == "running":
                was_running = True
                _set_progress(task_id, "running", 10, "Остановка сервера...")
                await stop_server(server_id)
                await asyncio.sleep(2)

        _set_progress(task_id, "running", 20, "Создание архива...")

        src = Path(server_dir)
        if not src.exists():
            _set_progress(task_id, "error", 0, f"Директория сервера не найдена: {server_dir}")
            return {"success": False, "error": "Server directory not found"}

        loop = asyncio.get_event_loop()
        result_path = await loop.run_in_executor(
            None, shutil.make_archive, str(archive_path), "zip", str(src)
        )

        file_size = os.path.getsize(result_path)
        _set_progress(task_id, "running", 60, "Архив создан")

        sftp_result = None
        if sftp_config and sftp_config.get("enabled"):
            _set_progress(task_id, "running", 65, "Подключение к SFTP...")
            sftp_result = await loop.run_in_executor(
                None, _upload_sftp, result_path, sftp_config, task_id
            )

        if was_running:
            _set_progress(task_id, "running", 90, "Запуск сервера...")
            if server_info:
                await start_server(
                    server_id, server_name, server_info["jar_file"],
                    java_path=server_info.get("java_path", "java"),
                    memory_min=server_info.get("memory_min", "1G"),
                    memory_max=server_info.get("memory_max", "2G"),
                    port=server_info.get("port", 25565),
                    jvm_args=server_info.get("jvm_args", ""),
                    mc_version=server_info.get("mc_version", "1.20.4"),
                )

        result = {
            "success": True,
            "path": result_path,
            "size": file_size,
            "timestamp": timestamp,
            "sftp": sftp_result,
        }
        _set_progress(task_id, "completed", 100, "Бекап завершён", **result)
        return result

    except Exception as e:
        logger.error(f"Backup failed for server {server_id}: {e}")
        _set_progress(task_id, "error", 0, str(e))

        if was_running and server_info:
            try:
                await start_server(
                    server_id, server_name, server_info["jar_file"],
                    java_path=server_info.get("java_path", "java"),
                    memory_min=server_info.get("memory_min", "1G"),
                    memory_max=server_info.get("memory_max", "2G"),
                    port=server_info.get("port", 25565),
                    jvm_args=server_info.get("jvm_args", ""),
                    mc_version=server_info.get("mc_version", "1.20.4"),
                )
            except Exception:
                pass

        return {"success": False, "error": str(e)}


def _upload_sftp(local_path: str, sftp_config: dict, task_id: str) -> dict:
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": sftp_config["host"],
            "port": sftp_config.get("port", 22),
            "username": sftp_config["username"],
            "timeout": 15,
        }

        key_path = sftp_config.get("key_path")
        if key_path:
            try:
                key = paramiko.RSAKey.from_private_key_file(key_path)
            except Exception:
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(key_path)
                except Exception:
                    key = paramiko.ECDSAKey.from_private_key_file(key_path)
            connect_kwargs["pkey"] = key
        elif sftp_config.get("password"):
            connect_kwargs["password"] = sftp_config["password"]

        client.connect(**connect_kwargs)
        sftp = client.open_sftp()

        remote_path = sftp_config.get("remote_path", "/backups")
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            _mkdir_p(sftp, remote_path)

        filename = os.path.basename(local_path)
        remote_file = f"{remote_path.rstrip('/')}/{filename}"

        file_size = os.path.getsize(local_path)

        def progress_callback(transferred, total):
            pct = int(65 + (transferred / total) * 25) if total > 0 else 65
            _set_progress(task_id, "running", pct, f"Загрузка SFTP: {transferred // (1024*1024)}MB / {total // (1024*1024)}MB")

        sftp.put(local_path, remote_file, callback=progress_callback)
        sftp.close()
        client.close()

        return {"success": True, "remote_path": remote_file}

    except Exception as e:
        logger.error(f"SFTP upload failed: {e}")
        return {"success": False, "error": str(e)}


def _mkdir_p(sftp, remote_path: str):
    dirs = []
    while remote_path not in ("", "/"):
        try:
            sftp.stat(remote_path)
            break
        except FileNotFoundError:
            dirs.append(remote_path)
            remote_path = os.path.dirname(remote_path)
    for d in reversed(dirs):
        try:
            sftp.mkdir(d)
        except OSError:
            pass


def list_backups(server_id: int = None) -> list[dict]:
    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        return []

    backups = []
    for f in backup_dir.glob("*.zip"):
        parts = f.stem.rsplit("_", 2)
        sid = None
        if len(parts) >= 3:
            try:
                sid = int(parts[-2])
            except ValueError:
                pass

        if server_id is not None and sid != server_id:
            continue

        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "server_id": sid,
        })

    backups.sort(key=lambda b: b["created"], reverse=True)
    return backups


def delete_backup(filename: str) -> bool:
    backup_dir = get_backup_dir()
    path = backup_dir / filename
    if path.exists() and path.parent == backup_dir:
        path.unlink()
        return True
    return False


def cleanup_old_backups(server_id: int, max_backups: int):
    backups = list_backups(server_id)
    if len(backups) > max_backups:
        for b in backups[max_backups:]:
            try:
                Path(b["path"]).unlink()
            except Exception:
                pass
