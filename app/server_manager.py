import os
import asyncio
import logging
import signal
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from app.config import SERVERS_DIR
from app.java_manager import find_suitable_java, check_java_available, get_required_java_version

logger = logging.getLogger("mineadmin.server")

_running_processes: dict[int, subprocess.Popen] = {}
_server_outputs: dict[int, list[str]] = {}
_output_locks: dict[int, asyncio.Lock] = {}
_ws_subscribers: dict[int, list[asyncio.Queue]] = {}


def get_server_dir(server_id: int, name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return SERVERS_DIR / f"{server_id}_{safe_name}"


def accept_eula(server_dir: Path):
    eula_file = server_dir / "eula.txt"
    eula_file.write_text("eula=true\n")


def update_server_properties(server_dir: Path, properties: dict):
    props_file = server_dir / "server.properties"
    lines = []
    existing = {}

    if props_file.exists():
        with open(props_file, "r") as f:
            for line in f:
                line = line.rstrip("\n")
                if "=" in line and not line.startswith("#"):
                    key = line.split("=", 1)[0]
                    existing[key] = len(lines)
                lines.append(line)

    for key, value in properties.items():
        if key in existing:
            lines[existing[key]] = f"{key}={value}"
        else:
            lines.append(f"{key}={value}")

    with open(props_file, "w") as f:
        f.write("\n".join(lines) + "\n")


def read_server_properties(server_dir: Path) -> dict:
    props_file = server_dir / "server.properties"
    props = {}
    if props_file.exists():
        with open(props_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()
    return props


async def start_server(server_id: int, name: str, jar_file: str,
                       java_path: str = "java", memory_min: str = "1G",
                       memory_max: str = "2G", port: int = 25565,
                       jvm_args: str = "", mc_version: str = "1.20.4") -> dict:
    if server_id in _running_processes:
        proc = _running_processes[server_id]
        if proc.poll() is None:
            return {"status": "already_running", "pid": proc.pid}

    server_dir = get_server_dir(server_id, name)
    server_dir.mkdir(parents=True, exist_ok=True)

    accept_eula(server_dir)

    props = read_server_properties(server_dir)
    props["server-port"] = str(port)
    update_server_properties(server_dir, props)

    if java_path == "java" or not java_path:
        found = find_suitable_java(mc_version)
        if found:
            java_path = found

    java_info = check_java_available(java_path)
    if not java_info:
        return {"status": "error", "message": f"Java not found at: {java_path}"}

    required = get_required_java_version(mc_version)
    if java_info["major_version"] < required:
        return {
            "status": "error",
            "message": f"Java {required}+ required, found {java_info['version']}"
        }

    cmd = [java_path]
    cmd.extend([f"-Xms{memory_min}", f"-Xmx{memory_max}"])

    if jvm_args:
        cmd.extend(jvm_args.split())

    cmd.extend(["-jar", jar_file, "nogui"])

    logger.info(f"Starting server {server_id}: {' '.join(cmd)}")

    _server_outputs[server_id] = []
    _output_locks[server_id] = asyncio.Lock()
    _ws_subscribers.setdefault(server_id, [])

    proc = subprocess.Popen(
        cmd,
        cwd=str(server_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    _running_processes[server_id] = proc

    asyncio.get_event_loop().run_in_executor(None, _read_output, server_id, proc)

    return {"status": "starting", "pid": proc.pid}


def _read_output(server_id: int, proc: subprocess.Popen):
    try:
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            line = line.rstrip("\n")
            if server_id in _server_outputs:
                _server_outputs[server_id].append(line)
                if len(_server_outputs[server_id]) > 5000:
                    _server_outputs[server_id] = _server_outputs[server_id][-3000:]

            for q in _ws_subscribers.get(server_id, []):
                try:
                    q.put_nowait(line)
                except asyncio.QueueFull:
                    pass
    except Exception as e:
        logger.error(f"Output reader error for server {server_id}: {e}")
    finally:
        proc.stdout.close()


async def send_command(server_id: int, command: str) -> bool:
    proc = _running_processes.get(server_id)
    if not proc or proc.poll() is not None:
        return False
    try:
        proc.stdin.write(command + "\n")
        proc.stdin.flush()
        return True
    except Exception as e:
        logger.error(f"Failed to send command to server {server_id}: {e}")
        return False


async def stop_server(server_id: int) -> dict:
    proc = _running_processes.get(server_id)
    if not proc or proc.poll() is not None:
        _running_processes.pop(server_id, None)
        return {"status": "not_running"}

    try:
        proc.stdin.write("stop\n")
        proc.stdin.flush()
    except Exception:
        pass

    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        if platform.system() == "Windows":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    _running_processes.pop(server_id, None)
    return {"status": "stopped"}


async def kill_server(server_id: int) -> dict:
    proc = _running_processes.get(server_id)
    if not proc or proc.poll() is not None:
        _running_processes.pop(server_id, None)
        return {"status": "not_running"}

    proc.kill()
    proc.wait(timeout=5)
    _running_processes.pop(server_id, None)
    return {"status": "killed"}


def get_server_status(server_id: int) -> str:
    proc = _running_processes.get(server_id)
    if not proc:
        return "stopped"
    if proc.poll() is None:
        return "running"
    _running_processes.pop(server_id, None)
    return "stopped"


def get_output(server_id: int, last_n: int = 200) -> list[str]:
    output = _server_outputs.get(server_id, [])
    return output[-last_n:]


def subscribe_output(server_id: int) -> asyncio.Queue:
    q = asyncio.Queue(maxsize=500)
    _ws_subscribers.setdefault(server_id, []).append(q)
    return q


def unsubscribe_output(server_id: int, q: asyncio.Queue):
    subs = _ws_subscribers.get(server_id, [])
    if q in subs:
        subs.remove(q)


def get_all_running() -> dict[int, int]:
    result = {}
    for sid, proc in list(_running_processes.items()):
        if proc.poll() is None:
            result[sid] = proc.pid
        else:
            _running_processes.pop(sid, None)
    return result


def get_used_ports() -> set[int]:
    ports = set()
    for sid, proc in _running_processes.items():
        if proc.poll() is None:
            ports.add(sid)
    return ports


def find_next_available_port(base_port: int = 25565, used_ports: set[int] = None) -> int:
    if used_ports is None:
        used_ports = set()
    port = base_port
    while port in used_ports:
        port += 1
    return port
