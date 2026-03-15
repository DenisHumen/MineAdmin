import ssl
import socket
import asyncio
import logging
import aiohttp
import certifi
from typing import Optional

logger = logging.getLogger("mineadmin.network")


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def get_public_ip() -> Optional[str]:
    services = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        text = text.strip()
                        if "json" in url:
                            import json
                            data = json.loads(text)
                            return data.get("ip", text)
                        return text
        except Exception:
            continue
    return None


def check_port_local(port: int, host: str = "0.0.0.0") -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port))
        sock.close()
        return result == 0
    except Exception:
        return False


def is_port_available(port: int) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.close()
        return True
    except OSError:
        return False


async def check_minecraft_server(host: str, port: int, timeout: float = 5) -> dict:
    result = {
        "online": False,
        "host": host,
        "port": port,
        "latency_ms": None,
        "error": None,
    }
    try:
        import time
        start = time.monotonic()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        latency = (time.monotonic() - start) * 1000
        result["online"] = True
        result["latency_ms"] = round(latency, 1)
        writer.close()
        await writer.wait_closed()
    except asyncio.TimeoutError:
        result["error"] = "Connection timed out"
    except ConnectionRefusedError:
        result["error"] = "Connection refused"
    except Exception as e:
        result["error"] = str(e)
    return result


async def full_network_check(port: int) -> dict:
    local_ip = get_local_ip()
    public_ip = await get_public_ip()

    local_check = await check_minecraft_server(local_ip, port)

    external_check = None
    if public_ip:
        external_check = await check_minecraft_server(public_ip, port, timeout=3)

    return {
        "local_ip": local_ip,
        "public_ip": public_ip,
        "port": port,
        "port_available": is_port_available(port) if not local_check["online"] else False,
        "local_accessible": local_check["online"],
        "local_latency_ms": local_check.get("latency_ms"),
        "external_accessible": external_check["online"] if external_check else None,
        "external_latency_ms": external_check.get("latency_ms") if external_check else None,
        "external_error": external_check.get("error") if external_check else "No public IP",
    }
