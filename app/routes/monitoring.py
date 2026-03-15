import logging
from fastapi import APIRouter, Depends
from app.routes.auth import get_current_user
from app.system_monitor import (
    get_system_info, get_system_stats, get_process_stats,
    get_java_processes, format_bytes,
)
from app.server_manager import get_all_running
from app.network_checker import get_local_ip, get_public_ip

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])
logger = logging.getLogger("mineadmin.routes.monitoring")


@router.get("/system")
async def system_info(user: dict = Depends(get_current_user)):
    info = get_system_info()
    info["total_ram"] = format_bytes(info["total_ram_bytes"])
    info["total_disk"] = format_bytes(info["total_disk_bytes"])
    return info


@router.get("/stats")
async def system_stats(user: dict = Depends(get_current_user)):
    stats = get_system_stats()
    stats["memory"]["total_formatted"] = format_bytes(stats["memory"]["total"])
    stats["memory"]["used_formatted"] = format_bytes(stats["memory"]["used"])
    stats["memory"]["available_formatted"] = format_bytes(stats["memory"]["available"])
    stats["disk"]["total_formatted"] = format_bytes(stats["disk"]["total"])
    stats["disk"]["used_formatted"] = format_bytes(stats["disk"]["used"])
    stats["disk"]["free_formatted"] = format_bytes(stats["disk"]["free"])
    return stats


@router.get("/servers")
async def server_processes(user: dict = Depends(get_current_user)):
    running = get_all_running()
    result = {}
    for server_id, pid in running.items():
        stats = get_process_stats(pid)
        if stats:
            stats["memory_formatted"] = format_bytes(stats["memory_rss"])
            result[server_id] = stats
    return {"servers": result}


@router.get("/java-processes")
async def java_procs(user: dict = Depends(get_current_user)):
    procs = get_java_processes()
    for p in procs:
        p["memory_formatted"] = format_bytes(p["memory_rss"])
    return {"processes": procs}


@router.get("/network")
async def network_info(user: dict = Depends(get_current_user)):
    local_ip = get_local_ip()
    public_ip = await get_public_ip()
    return {
        "local_ip": local_ip,
        "public_ip": public_ip,
    }
