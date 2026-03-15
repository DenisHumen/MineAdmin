import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Server
from app.routes.auth import get_current_user
from app.server_manager import (
    start_server, stop_server, kill_server, get_server_status,
    get_server_dir, send_command, get_output, get_all_running,
    find_next_available_port, read_server_properties, update_server_properties,
)
from app.downloader import (
    get_available_versions, download_server, get_progress,
    clear_progress, CORE_TYPES,
)
from app.java_manager import (
    find_java_installations, find_suitable_java,
    get_java_install_instructions, get_required_java_version,
    find_suitable_java_for_spigot, get_spigot_java_range,
    auto_install_java, get_java_install_progress,
)
from app.network_checker import full_network_check
from app.system_monitor import get_process_stats
from app.config import SERVERS_DIR

router = APIRouter(prefix="/api/servers", tags=["servers"])
logger = logging.getLogger("mineadmin.routes.servers")


@router.get("/core-types")
async def list_core_types(user: dict = Depends(get_current_user)):
    descriptions = {
        "vanilla": "Official Minecraft Server",
        "paper": "PaperMC - High performance Spigot fork",
        "purpur": "Purpur - Paper fork with extra features",
        "fabric": "Fabric - Lightweight modding platform",
        "forge": "Forge - Popular modding platform",
        "spigot": "Spigot - CraftBukkit fork with optimizations",
    }
    return [{"id": ct, "name": ct.capitalize(), "description": descriptions.get(ct, "")}
            for ct in CORE_TYPES]


@router.get("/versions/{core_type}")
async def list_versions(core_type: str, user: dict = Depends(get_current_user)):
    if core_type not in CORE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown core type: {core_type}")
    versions = await get_available_versions(core_type)
    return {"core_type": core_type, "versions": versions}


@router.get("/java")
async def list_java(user: dict = Depends(get_current_user)):
    installations = find_java_installations()
    return {"installations": installations}


@router.get("/java/requirements/{mc_version}")
async def java_requirements(mc_version: str, core_type: str = "vanilla",
                            user: dict = Depends(get_current_user)):
    required = get_required_java_version(mc_version)
    suitable = find_suitable_java(mc_version)
    instructions = get_java_install_instructions(required)
    result = {
        "mc_version": mc_version,
        "required_java": required,
        "suitable_java_path": suitable,
        "install_instructions": instructions,
    }
    if core_type == "spigot":
        min_j, max_j = get_spigot_java_range(mc_version)
        spigot_java = find_suitable_java_for_spigot(mc_version)
        result["spigot_build"] = {
            "min_java": min_j,
            "max_java": max_j,
            "suitable_java_path": spigot_java,
        }
    return result


@router.post("/java/install")
async def install_java(request: Request,
                       background_tasks: BackgroundTasks,
                       user: dict = Depends(get_current_user)):
    data = await request.json()
    required_version = data.get("required_version", 21)
    task_id = f"java_install_{required_version}"

    async def do_install():
        await auto_install_java(required_version, task_id)

    background_tasks.add_task(do_install)
    return {"task_id": task_id, "status": "started"}


@router.get("/java/install-progress/{task_id}")
async def java_progress(task_id: str, user: dict = Depends(get_current_user)):
    return get_java_install_progress(task_id)


@router.get("/java/check/{core_type}/{mc_version}")
async def check_java_for_server(core_type: str, mc_version: str,
                                user: dict = Depends(get_current_user)):
    required = get_required_java_version(mc_version)
    suitable = find_suitable_java(mc_version)
    instructions = get_java_install_instructions(required)

    result = {
        "available": suitable is not None,
        "required_version": required,
        "found_path": suitable,
        "install_instructions": instructions,
        "installations": find_java_installations(),
    }

    if core_type == "spigot":
        min_j, max_j = get_spigot_java_range(mc_version)
        spigot_java = find_suitable_java_for_spigot(mc_version)
        result["spigot_build"] = {
            "min_java": min_j,
            "max_java": max_j,
            "suitable_java_path": spigot_java,
            "available": spigot_java is not None,
        }
        if not spigot_java:
            result["available"] = False
            result["required_version_text"] = f"Java {min_j}-{max_j} (для BuildTools)"
            instructions = get_java_install_instructions(min_j)
            result["install_instructions"] = instructions

    return result


@router.get("")
async def list_servers(session: AsyncSession = Depends(get_session),
                       user: dict = Depends(get_current_user)):
    result = await session.execute(select(Server))
    servers = result.scalars().all()
    running = get_all_running()

    server_list = []
    for s in servers:
        status = get_server_status(s.id)
        if s.status != status:
            s.status = status
            await session.commit()
        data = {
            "id": s.id, "name": s.name, "core_type": s.core_type,
            "mc_version": s.mc_version, "port": s.port,
            "max_players": s.max_players, "memory_min": s.memory_min,
            "memory_max": s.memory_max, "status": status,
            "pid": running.get(s.id), "auto_restart": s.auto_restart,
            "java_path": s.java_path, "jvm_args": s.jvm_args,
        }
        if s.id in running:
            stats = get_process_stats(running[s.id])
            if stats:
                data["process_stats"] = stats
        server_list.append(data)

    return {"servers": server_list}


@router.post("")
async def create_server(request: Request,
                        background_tasks: BackgroundTasks,
                        session: AsyncSession = Depends(get_session),
                        user: dict = Depends(get_current_user)):
    data = await request.json()
    name = data.get("name", "").strip()
    core_type = data.get("core_type", "")
    mc_version = data.get("mc_version", "")
    port = data.get("port")
    memory_min = data.get("memory_min", "1G")
    memory_max = data.get("memory_max", "2G")
    max_players = data.get("max_players", 20)

    if not name:
        raise HTTPException(status_code=400, detail="Server name required")
    if core_type not in CORE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid core type: {core_type}")

    existing = await session.execute(select(Server).where(Server.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Server '{name}' already exists")

    if port is None:
        used_ports = set()
        all_servers = await session.execute(select(Server))
        for s in all_servers.scalars().all():
            used_ports.add(s.port)
        port = find_next_available_port(25565, used_ports)

    server = Server(
        name=name, core_type=core_type, mc_version=mc_version,
        port=port, memory_min=memory_min, memory_max=memory_max,
        max_players=max_players, server_dir="", jar_file="",
        status="installing",
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)

    server_dir = get_server_dir(server.id, name)
    server.server_dir = str(server_dir)
    await session.commit()

    task_id = f"install_{server.id}"

    async def install_task():
        async with async_session_factory() as s:
            try:
                srv = await s.get(Server, server.id)
                jar_path = await download_server(core_type, mc_version, server_dir, task_id)
                srv.jar_file = jar_path.name
                srv.server_dir = str(server_dir)
                srv.status = "stopped"
                await s.commit()
            except Exception as e:
                logger.error(f"Install failed for server {server.id}: {e}")
                srv = await s.get(Server, server.id)
                srv.status = "error"
                srv.extra_config = {"install_error": str(e)}
                await s.commit()

    from app.database import async_session as async_session_factory
    background_tasks.add_task(install_task)

    return {
        "id": server.id, "name": name, "status": "installing",
        "task_id": task_id, "port": port,
    }


@router.get("/install-progress/{task_id}")
async def install_progress(task_id: str, user: dict = Depends(get_current_user)):
    progress = get_progress(task_id)
    return progress.to_dict()


@router.post("/{server_id}/start")
async def start(server_id: int,
                session: AsyncSession = Depends(get_session),
                user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if server.status == "installing":
        raise HTTPException(status_code=400, detail="Server is still installing")

    result = await start_server(
        server.id, server.name, server.jar_file,
        java_path=server.java_path, memory_min=server.memory_min,
        memory_max=server.memory_max, port=server.port,
        jvm_args=server.jvm_args, mc_version=server.mc_version,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    server.status = "running"
    server.pid = result.get("pid")
    await session.commit()
    return result


@router.post("/{server_id}/stop")
async def stop(server_id: int,
               session: AsyncSession = Depends(get_session),
               user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    result = await stop_server(server_id)
    server.status = "stopped"
    server.pid = None
    await session.commit()
    return result


@router.post("/{server_id}/kill")
async def force_kill(server_id: int,
                     session: AsyncSession = Depends(get_session),
                     user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    result = await kill_server(server_id)
    server.status = "stopped"
    server.pid = None
    await session.commit()
    return result


@router.post("/{server_id}/command")
async def run_command(server_id: int, request: Request,
                      user: dict = Depends(get_current_user)):
    data = await request.json()
    command = data.get("command", "")
    if not command:
        raise HTTPException(status_code=400, detail="Command required")
    success = await send_command(server_id, command)
    if not success:
        raise HTTPException(status_code=400, detail="Server not running")
    return {"success": True}


@router.get("/{server_id}/output")
async def server_output(server_id: int, lines: int = 200,
                        user: dict = Depends(get_current_user)):
    output = get_output(server_id, lines)
    return {"output": output}


@router.get("/{server_id}/properties")
async def get_properties(server_id: int,
                         session: AsyncSession = Depends(get_session),
                         user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server_dir = Path(server.server_dir)
    props = read_server_properties(server_dir)
    return {"properties": props}


@router.put("/{server_id}/properties")
async def set_properties(server_id: int, request: Request,
                         session: AsyncSession = Depends(get_session),
                         user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    data = await request.json()
    server_dir = Path(server.server_dir)
    update_server_properties(server_dir, data.get("properties", {}))
    return {"success": True}


@router.put("/{server_id}")
async def update_server(server_id: int, request: Request,
                        session: AsyncSession = Depends(get_session),
                        user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    data = await request.json()
    for field in ["name", "port", "memory_min", "memory_max", "max_players",
                  "java_path", "jvm_args", "auto_restart"]:
        if field in data:
            setattr(server, field, data[field])
    await session.commit()
    return {"success": True}


@router.delete("/{server_id}")
async def delete_server(server_id: int,
                        session: AsyncSession = Depends(get_session),
                        user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if get_server_status(server_id) == "running":
        await stop_server(server_id)

    import shutil
    server_dir = Path(server.server_dir)
    if server_dir.exists():
        shutil.rmtree(server_dir)

    await session.delete(server)
    await session.commit()
    return {"success": True}


@router.get("/{server_id}/network")
async def check_network(server_id: int,
                        session: AsyncSession = Depends(get_session),
                        user: dict = Depends(get_current_user)):
    server = await session.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    result = await full_network_check(server.port)
    return result
