import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session, export_data, import_data, init_db, async_session
from app.models import AppSettings
from app.routes.auth import get_current_user
from app.config import load_config, save_config

router = APIRouter(prefix="/api/config", tags=["config"])
logger = logging.getLogger("mineadmin.routes.config")

_version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"


@router.get("/version")
async def get_version():
    try:
        return {"version": _version_file.read_text().strip()}
    except Exception:
        return {"version": "unknown"}


@router.get("")
async def get_config(user: dict = Depends(get_current_user)):
    cfg = load_config()
    safe_cfg = {k: v for k, v in cfg.items() if k != "secret_key"}
    if "mysql" in safe_cfg and safe_cfg["mysql"].get("password"):
        safe_cfg["mysql"] = {**safe_cfg["mysql"], "password": "***"}
    return {"config": safe_cfg}


@router.put("")
async def update_config(request: Request, user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    data = await request.json()
    cfg = load_config()

    for key in ["db_type", "default_java_memory", "max_java_memory", "servers_dir"]:
        if key in data:
            cfg[key] = data[key]

    if "backup" in data:
        if "backup" not in cfg:
            cfg["backup"] = {}
        for k in ["path"]:
            if k in data["backup"]:
                cfg["backup"][k] = data["backup"][k]
        if "sftp" in data["backup"]:
            if "sftp" not in cfg["backup"]:
                cfg["backup"]["sftp"] = {}
            for k in ["enabled", "host", "port", "username", "key_path", "remote_path"]:
                if k in data["backup"]["sftp"]:
                    cfg["backup"]["sftp"][k] = data["backup"]["sftp"][k]
            if "password" in data["backup"]["sftp"] and data["backup"]["sftp"]["password"] != "***":
                cfg["backup"]["sftp"]["password"] = data["backup"]["sftp"]["password"]
        if "schedule" in data["backup"]:
            if "schedule" not in cfg["backup"]:
                cfg["backup"]["schedule"] = {}
            for k in ["enabled", "interval_hours", "max_backups"]:
                if k in data["backup"]["schedule"]:
                    cfg["backup"]["schedule"][k] = data["backup"]["schedule"][k]

    if "mysql" in data:
        for k in ["host", "port", "user", "password", "database"]:
            if k in data["mysql"]:
                if k == "password" and data["mysql"][k] == "***":
                    continue
                cfg["mysql"][k] = data["mysql"][k]

    if "web" in data:
        for k in ["host", "port"]:
            if k in data["web"]:
                cfg["web"][k] = data["web"][k]

    save_config(cfg)
    return {"success": True}


@router.post("/switch-db")
async def switch_database(request: Request, user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    data = await request.json()
    new_type = data.get("db_type", "sqlite")
    cfg = load_config()

    if new_type == cfg.get("db_type"):
        return {"success": True, "message": "Already using this database type"}

    try:
        async with async_session() as session:
            current_data = await export_data(session)
    except Exception as e:
        current_data = None
        logger.warning(f"Failed to export current data: {e}")

    if new_type == "mysql":
        if "mysql" in data:
            for k in ["host", "port", "user", "password", "database"]:
                if k in data["mysql"]:
                    cfg["mysql"][k] = data["mysql"][k]

    cfg["db_type"] = new_type
    save_config(cfg)

    try:
        await init_db()

        if current_data:
            async with async_session() as session:
                await import_data(session, current_data)

        return {"success": True, "message": f"Switched to {new_type}"}
    except Exception as e:
        cfg["db_type"] = "sqlite"
        save_config(cfg)
        await init_db()

        return {
            "success": False,
            "message": f"Failed to switch to {new_type}: {str(e)}. Reverted to SQLite.",
            "error": str(e),
            "help_url": "/docs#database-troubleshooting"
        }


@router.get("/db-status")
async def db_status(user: dict = Depends(get_current_user)):
    cfg = load_config()
    mysql_error = cfg.get("_mysql_error")
    return {
        "db_type": cfg.get("db_type", "sqlite"),
        "mysql_error": mysql_error,
        "mysql_configured": bool(cfg.get("mysql", {}).get("host")),
    }


@router.post("/export")
async def export_db(session: AsyncSession = Depends(get_session),
                    user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    data = await export_data(session)
    return {"data": data}


@router.post("/import")
async def import_db(request: Request,
                    session: AsyncSession = Depends(get_session),
                    user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    data = await request.json()
    await import_data(session, data.get("data", {}))
    return {"success": True}


@router.get("/ssh")
async def get_ssh_config(user: dict = Depends(get_current_user)):
    import platform
    cfg = load_config()
    ssh = cfg.get("ssh", {})
    safe_ssh = {**ssh}
    if safe_ssh.get("password"):
        safe_ssh["password"] = "***"
    return {
        "ssh": safe_ssh,
        "system": platform.system(),
        "ssh_available": platform.system() == "Linux",
    }


@router.put("/ssh")
async def update_ssh_config(request: Request, user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    data = await request.json()
    cfg = load_config()
    ssh = cfg.get("ssh", {})
    for k in ["enabled", "host", "port", "username", "auth_type", "key_path"]:
        if k in data:
            ssh[k] = data[k]
    if "password" in data and data["password"] != "***":
        ssh["password"] = data["password"]
    cfg["ssh"] = ssh
    save_config(cfg)
    return {"success": True}


@router.post("/ssh/test")
async def test_ssh(request: Request, user: dict = Depends(get_current_user)):
    data = await request.json()
    from app.ssh_manager import test_ssh_connection
    result = test_ssh_connection(
        host=data.get("host", "localhost"),
        port=data.get("port", 22),
        username=data.get("username", ""),
        password=data.get("password"),
        key_path=data.get("key_path"),
    )
    return result
