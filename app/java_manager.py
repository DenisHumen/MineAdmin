import os
import re
import ssl
import shutil
import logging
import platform
import subprocess
import asyncio
from pathlib import Path
from typing import Optional

import aiohttp
import certifi

logger = logging.getLogger("mineadmin.java")

MC_JAVA_REQUIREMENTS = {
    "1.21": 21, "1.20.5": 21, "1.20": 17, "1.19": 17, "1.18": 17,
    "1.17": 16, "1.16": 11, "1.15": 8, "1.14": 8, "1.13": 8,
    "1.12": 8, "1.11": 8, "1.10": 8, "1.9": 8, "1.8": 8, "1.7": 8,
}

SPIGOT_JAVA_RANGE = {
    "1.21": (21, 25), "1.20.5": (21, 25), "1.20": (17, 25),
    "1.19": (17, 21), "1.18": (17, 21), "1.17": (16, 21),
    "1.16": (8, 16), "1.15": (8, 16), "1.14": (8, 16), "1.13": (8, 16),
    "1.12": (8, 16), "1.11": (8, 16), "1.10": (8, 16), "1.9": (8, 16),
    "1.8": (8, 16), "1.7": (8, 16),
}

_java_install_progress: dict[str, dict] = {}


def get_java_install_progress(task_id: str) -> dict:
    return _java_install_progress.get(task_id, {
        "status": "idle", "percent": 0, "message": "", "error": ""
    })


def get_required_java_version(mc_version: str) -> int:
    parts = mc_version.split(".")
    for i in range(len(parts), 0, -1):
        key = ".".join(parts[:i])
        if key in MC_JAVA_REQUIREMENTS:
            return MC_JAVA_REQUIREMENTS[key]
    try:
        minor = int(parts[1]) if len(parts) > 1 else 0
        if minor >= 21:
            return 21
        if minor >= 17:
            return 17
    except (ValueError, IndexError):
        pass
    return 17


def get_spigot_java_range(mc_version: str) -> tuple[int, int]:
    parts = mc_version.split(".")
    for i in range(len(parts), 0, -1):
        key = ".".join(parts[:i])
        if key in SPIGOT_JAVA_RANGE:
            return SPIGOT_JAVA_RANGE[key]
    return (17, 25)


def find_java_installations() -> list[dict]:
    installations = []
    seen = set()

    java_in_path = shutil.which("java")
    if java_in_path:
        info = _get_java_info(java_in_path)
        if info and info["path"] not in seen:
            seen.add(info["path"])
            installations.append(info)

    system = platform.system()

    search_paths = []
    if system == "Linux":
        search_paths = [
            Path("/usr/lib/jvm"),
            Path("/usr/java"),
            Path("/opt/java"),
            Path("/opt/jdk"),
            Path.home() / ".sdkman/candidates/java",
        ]
    elif system == "Darwin":
        search_paths = [
            Path("/Library/Java/JavaVirtualMachines"),
            Path("/usr/local/opt"),
            Path.home() / ".sdkman/candidates/java",
            Path("/opt/homebrew/opt"),
        ]
    elif system == "Windows":
        for drive in ["C:", "D:"]:
            search_paths.extend([
                Path(f"{drive}/Program Files/Java"),
                Path(f"{drive}/Program Files/Eclipse Adoptium"),
                Path(f"{drive}/Program Files/Zulu"),
                Path(f"{drive}/Program Files/Microsoft"),
            ])

    for base in search_paths:
        if not base.exists():
            continue
        for entry in base.iterdir():
            if entry.is_dir():
                for bin_name in ["java", "java.exe"]:
                    java_bin = entry / "bin" / bin_name
                    if not java_bin.exists():
                        java_bin = entry / "Contents/Home/bin" / bin_name
                    if java_bin.exists():
                        info = _get_java_info(str(java_bin))
                        if info and info["path"] not in seen:
                            seen.add(info["path"])
                            installations.append(info)

    return sorted(installations, key=lambda x: x.get("major_version", 0), reverse=True)


def _get_java_info(java_path: str) -> Optional[dict]:
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stderr + result.stdout
        match = re.search(r'version "([^"]+)"', output)
        if match:
            version_str = match.group(1)
            major = _parse_major_version(version_str)
            return {
                "path": java_path,
                "version": version_str,
                "major_version": major,
            }
    except Exception as e:
        logger.debug(f"Failed to get Java info from {java_path}: {e}")
    return None


def _parse_major_version(version_str: str) -> int:
    parts = version_str.split(".")
    try:
        first = int(parts[0])
        if first == 1 and len(parts) > 1:
            return int(parts[1])
        return first
    except ValueError:
        return 0


def find_suitable_java(mc_version: str) -> Optional[str]:
    required = get_required_java_version(mc_version)
    installations = find_java_installations()
    for inst in installations:
        if inst["major_version"] >= required:
            return inst["path"]
    return None


def find_suitable_java_for_spigot(mc_version: str) -> Optional[str]:
    min_java, max_java = get_spigot_java_range(mc_version)
    installations = find_java_installations()
    suitable = [i for i in installations if min_java <= i["major_version"] <= max_java]
    if not suitable:
        return None
    suitable.sort(key=lambda x: x["major_version"], reverse=True)
    return suitable[0]["path"]


def check_java_available(java_path: str = "java") -> Optional[dict]:
    return _get_java_info(java_path)


def get_java_install_instructions(required_version: int) -> dict:
    system = platform.system()
    instructions = {
        "required_version": required_version,
        "system": system,
        "commands": [],
        "links": [],
        "auto_available": False,
    }

    if system == "Linux":
        instructions["commands"] = [
            f"sudo apt update && sudo apt install -y openjdk-{required_version}-jre-headless",
            f"sudo yum install -y java-{required_version}-openjdk-headless",
            f"sudo pacman -S jre{required_version}-openjdk-headless",
        ]
        instructions["auto_available"] = True
    elif system == "Darwin":
        instructions["commands"] = [
            f"brew install openjdk@{required_version}",
        ]
        instructions["auto_available"] = shutil.which("brew") is not None
    elif system == "Windows":
        instructions["commands"] = [
            f"winget install EclipseAdoptium.Temurin.{required_version}.JRE",
        ]
        instructions["auto_available"] = shutil.which("winget") is not None

    instructions["links"] = [
        f"https://adoptium.net/temurin/releases/?version={required_version}",
        "https://www.oracle.com/java/technologies/downloads/",
    ]
    return instructions


def _get_adoptium_url(version: int) -> str:
    system = platform.system().lower()
    arch = platform.machine().lower()
    os_map = {"linux": "linux", "darwin": "mac", "windows": "windows"}
    arch_map = {"x86_64": "x64", "amd64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}
    os_name = os_map.get(system, "linux")
    arch_name = arch_map.get(arch, "x64")
    return (
        f"https://api.adoptium.net/v3/assets/latest/{version}/hotspot"
        f"?architecture={arch_name}&image_type=jre&os={os_name}&vendor=eclipse"
    )


async def auto_install_java(required_version: int, task_id: str) -> dict:
    progress = {"status": "starting", "percent": 0, "message": "", "error": ""}
    _java_install_progress[task_id] = progress

    system = platform.system()
    result = {"status": "error", "message": "", "java_path": None}

    try:
        if system == "Linux":
            result = await _install_java_linux(required_version, progress)
        elif system == "Darwin":
            result = await _install_java_macos(required_version, progress)
        elif system == "Windows":
            result = await _install_java_windows(required_version, progress)
        else:
            result["message"] = f"Автоустановка не поддерживается на {system}"

        if result["status"] == "installed":
            progress["status"] = "completed"
            progress["percent"] = 100
            progress["message"] = f"Java {required_version} установлена"
        else:
            progress["status"] = "error"
            progress["error"] = result["message"]

    except Exception as e:
        logger.error(f"Java install error: {e}")
        progress["status"] = "error"
        progress["error"] = str(e)
        result["message"] = str(e)

    _java_install_progress[task_id] = progress
    return result


async def _install_java_linux(version: int, progress: dict) -> dict:
    progress["status"] = "installing"
    progress["message"] = "Определение пакетного менеджера..."
    progress["percent"] = 10

    pkg_managers = [
        {
            "check": "apt",
            "commands": [
                ["sudo", "apt-get", "update", "-y"],
                ["sudo", "apt-get", "install", "-y", f"openjdk-{version}-jre-headless"],
            ],
            "name": "apt"
        },
        {
            "check": "yum",
            "commands": [
                ["sudo", "yum", "install", "-y", f"java-{version}-openjdk-headless"],
            ],
            "name": "yum"
        },
        {
            "check": "dnf",
            "commands": [
                ["sudo", "dnf", "install", "-y", f"java-{version}-openjdk-headless"],
            ],
            "name": "dnf"
        },
        {
            "check": "pacman",
            "commands": [
                ["sudo", "pacman", "-S", "--noconfirm", f"jre{version}-openjdk-headless"],
            ],
            "name": "pacman"
        },
    ]

    for pm in pkg_managers:
        if shutil.which(pm["check"]):
            progress["message"] = f"Установка через {pm['name']}..."
            progress["percent"] = 30

            for i, cmd in enumerate(pm["commands"]):
                progress["percent"] = 30 + (i + 1) * 30 // len(pm["commands"])
                progress["message"] = f"Выполняется: {' '.join(cmd[:4])}..."
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0 and cmd[1] != "apt-get":
                    return {"status": "error", "message": stderr.decode(), "java_path": None}

            progress["percent"] = 80
            progress["message"] = "Проверка установки..."

            java_path = find_suitable_java_by_version(version)
            if java_path:
                return {"status": "installed", "message": "OK", "java_path": java_path}
            return {"status": "error", "message": f"Java {version} не найдена после установки", "java_path": None}

    return {"status": "error", "message": "Пакетный менеджер не найден (apt/yum/dnf/pacman)", "java_path": None}


async def _install_java_macos(version: int, progress: dict) -> dict:
    if shutil.which("brew"):
        progress["status"] = "installing"
        progress["message"] = f"brew install openjdk@{version}..."
        progress["percent"] = 30

        proc = await asyncio.create_subprocess_exec(
            "brew", "install", f"openjdk@{version}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        progress["percent"] = 80

        if proc.returncode != 0:
            return {"status": "error", "message": stderr.decode(), "java_path": None}

        progress["message"] = "Проверка установки..."
        java_path = find_suitable_java_by_version(version)
        if java_path:
            return {"status": "installed", "message": "OK", "java_path": java_path}

    return await _download_adoptium_installer(version, progress)


async def _install_java_windows(version: int, progress: dict) -> dict:
    if shutil.which("winget"):
        progress["status"] = "installing"
        progress["message"] = f"winget install Temurin {version}..."
        progress["percent"] = 30

        proc = await asyncio.create_subprocess_exec(
            "winget", "install", "--accept-package-agreements", "--accept-source-agreements",
            f"EclipseAdoptium.Temurin.{version}.JRE",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        progress["percent"] = 80

        if proc.returncode == 0:
            progress["message"] = "Проверка установки..."
            java_path = find_suitable_java_by_version(version)
            if java_path:
                return {"status": "installed", "message": "OK", "java_path": java_path}

    return await _download_adoptium_installer(version, progress)


async def _download_adoptium_installer(version: int, progress: dict) -> dict:
    progress["status"] = "downloading"
    progress["message"] = f"Скачивание установщика Java {version}..."
    progress["percent"] = 20

    try:
        url = _get_adoptium_url(version)
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if not data:
            return {"status": "error", "message": "Установщик не найден на Adoptium", "java_path": None}

        binary = data[0].get("binary", {})
        pkg = binary.get("package", {})
        download_url = pkg.get("link")
        filename = pkg.get("name", f"java-{version}-installer")

        if not download_url:
            return {"status": "error", "message": "Ссылка на загрузку не найдена", "java_path": None}

        progress["percent"] = 40
        progress["message"] = f"Скачивание {filename}..."

        import tempfile
        dest = Path(tempfile.gettempdir()) / filename

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
            async with session.get(download_url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            progress["percent"] = 40 + int((downloaded / total) * 40)

        progress["percent"] = 85
        progress["message"] = f"Установщик скачан: {dest}"

        system = platform.system()
        if system == "Linux" and filename.endswith(".tar.gz"):
            progress["message"] = "Распаковка..."
            import tarfile
            extract_dir = Path("/opt") / f"java-{version}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(dest) as tar:
                tar.extractall(extract_dir, filter='data')
            for java_bin in extract_dir.rglob("bin/java"):
                info = _get_java_info(str(java_bin))
                if info and info["major_version"] == version:
                    return {"status": "installed", "message": "OK", "java_path": str(java_bin)}

        progress["status"] = "downloaded"
        progress["percent"] = 90
        return {
            "status": "downloaded",
            "message": f"Установщик скачан: {dest}. Запустите его вручную.",
            "java_path": None,
            "installer_path": str(dest),
        }

    except Exception as e:
        return {"status": "error", "message": f"Ошибка загрузки: {e}", "java_path": None}


def find_suitable_java_by_version(version: int) -> Optional[str]:
    installations = find_java_installations()
    for inst in installations:
        if inst["major_version"] == version:
            return inst["path"]
    for inst in installations:
        if inst["major_version"] >= version:
            return inst["path"]
    return None
