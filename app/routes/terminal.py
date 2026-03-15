import asyncio
import json
import logging
import platform
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import app.database as db
from app.models import Server
from app.server_manager import (
    send_command, get_output, subscribe_output, unsubscribe_output,
    get_server_status,
)
from app.routes.auth import decode_token
from app.config import load_config

router = APIRouter(tags=["terminal"])
logger = logging.getLogger("mineadmin.routes.terminal")

MC_COMMANDS = [
    "help", "stop", "save-all", "save-on", "save-off", "list",
    "say", "tell", "msg", "w", "me", "kick", "ban", "ban-ip",
    "pardon", "pardon-ip", "op", "deop", "whitelist",
    "gamemode", "difficulty", "defaultgamemode",
    "tp", "teleport", "give", "clear", "effect", "enchant",
    "experience", "xp", "kill", "summon", "setblock", "fill",
    "clone", "time", "weather", "gamerule", "seed", "worldborder",
    "spawnpoint", "setworldspawn", "title", "scoreboard",
    "advancement", "reload", "data", "execute", "function",
    "locate", "playsound", "particle", "recipe", "tag",
    "team", "trigger", "bossbar", "forceload", "schedule",
    "spreadplayers", "stopsound", "loot", "attribute",
]


@router.websocket("/ws/terminal/{server_id}")
async def terminal_ws(websocket: WebSocket, server_id: int):
    token = websocket.query_params.get("token", "")
    try:
        user = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    async with db.async_session() as session:
        server = await session.get(Server, server_id)
        if not server:
            await websocket.send_json({"type": "error", "message": "Server not found"})
            await websocket.close()
            return

    history = get_output(server_id, 500)
    await websocket.send_json({"type": "history", "lines": history})

    await websocket.send_json({
        "type": "autocomplete_commands",
        "commands": MC_COMMANDS
    })

    queue = subscribe_output(server_id)

    async def send_output():
        try:
            while True:
                line = await queue.get()
                await websocket.send_json({"type": "output", "line": line})
        except Exception:
            pass

    output_task = asyncio.create_task(send_output())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"type": "command", "command": data}

            if msg.get("type") == "command":
                command = msg.get("command", "").strip()
                if command:
                    status = get_server_status(server_id)
                    if status == "running":
                        await send_command(server_id, command)
                        await websocket.send_json({
                            "type": "command_sent",
                            "command": command
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Server is not running"
                        })
            elif msg.get("type") == "autocomplete":
                prefix = msg.get("prefix", "")
                matches = [c for c in MC_COMMANDS if c.startswith(prefix.lower())]
                await websocket.send_json({
                    "type": "autocomplete_result",
                    "matches": matches[:20]
                })
            elif msg.get("type") == "status":
                status = get_server_status(server_id)
                await websocket.send_json({
                    "type": "status",
                    "status": status
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Terminal WS error: {e}")
    finally:
        output_task.cancel()
        unsubscribe_output(server_id, queue)


@router.websocket("/ws/system-terminal")
async def system_terminal_ws(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    try:
        user = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if platform.system() != "Linux":
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "Системный терминал доступен только на Linux"
        })
        await websocket.close()
        return

    cfg = load_config()
    ssh_cfg = cfg.get("ssh", {})

    if not ssh_cfg.get("enabled"):
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "SSH терминал отключён. Включите в Настройки → SSH"
        })
        await websocket.close()
        return

    from app.ssh_manager import SSHSession
    session = SSHSession()

    password = ssh_cfg.get("password") if ssh_cfg.get("auth_type") == "password" else None
    key_path = ssh_cfg.get("key_path") if ssh_cfg.get("auth_type") == "key" else None

    result = session.connect(
        host=ssh_cfg.get("host", "localhost"),
        port=ssh_cfg.get("port", 22),
        username=ssh_cfg.get("username", ""),
        password=password,
        key_path=key_path,
    )

    if not result["success"]:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": result["error"]})
        await websocket.close()
        return

    await websocket.accept()
    await websocket.send_json({"type": "connected", "message": "SSH подключён"})

    async def read_ssh_output():
        try:
            while session.connected:
                data = await session.read()
                if data:
                    await websocket.send_json({"type": "output", "data": data})
                else:
                    await asyncio.sleep(0.05)
        except Exception:
            pass

    read_task = asyncio.create_task(read_ssh_output())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"type": "input", "data": raw}

            if msg.get("type") == "input":
                await session.write(msg.get("data", ""))
            elif msg.get("type") == "resize":
                session.resize(
                    msg.get("cols", 120),
                    msg.get("rows", 40)
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"System terminal WS error: {e}")
    finally:
        read_task.cancel()
        session.close()
