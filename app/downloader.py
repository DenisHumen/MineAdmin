import os
import ssl
import logging
import aiohttp
import asyncio
import certifi
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mineadmin.downloader")

MOJANG_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
PAPER_API = "https://api.papermc.io/v2"
PURPUR_API = "https://api.purpurmc.org/v2"
FABRIC_META = "https://meta.fabricmc.net/v2"
FORGE_MAVEN = "https://files.minecraftforge.net/net/minecraftforge/forge"
SPIGOT_DOWNLOAD = "https://download.getbukkit.org/spigot"

CORE_TYPES = ["vanilla", "paper", "purpur", "fabric", "forge", "spigot"]


def _ssl_ctx() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


class DownloadProgress:
    def __init__(self):
        self.total = 0
        self.downloaded = 0
        self.status = "idle"
        self.filename = ""
        self.error = ""

    @property
    def percent(self) -> float:
        if self.status == "completed":
            return 100.0
        if self.total == 0:
            if self.downloaded > 0:
                estimated = min(95.0, round((self.downloaded / (50 * 1024 * 1024)) * 100, 1))
                return estimated
            return 0
        return round((self.downloaded / self.total) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "downloaded": self.downloaded,
            "percent": self.percent,
            "status": self.status,
            "filename": self.filename,
            "error": self.error,
        }


_progress_store: dict[str, DownloadProgress] = {}


def get_progress(task_id: str) -> DownloadProgress:
    if task_id not in _progress_store:
        _progress_store[task_id] = DownloadProgress()
    return _progress_store[task_id]


def clear_progress(task_id: str):
    _progress_store.pop(task_id, None)


async def fetch_json(url: str, timeout: int = 30) -> dict | list:
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_ctx())) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_vanilla_versions() -> list[dict]:
    data = await fetch_json(MOJANG_MANIFEST)
    versions = []
    for v in data.get("versions", []):
        if v["type"] in ("release", "snapshot"):
            versions.append({
                "id": v["id"],
                "type": v["type"],
                "url": v["url"],
            })
    return versions


async def get_paper_versions() -> list[str]:
    data = await fetch_json(f"{PAPER_API}/projects/paper")
    return list(reversed(data.get("versions", [])))


async def get_paper_builds(version: str) -> list[int]:
    data = await fetch_json(f"{PAPER_API}/projects/paper/versions/{version}")
    return data.get("builds", [])


async def get_purpur_versions() -> list[str]:
    data = await fetch_json(f"{PURPUR_API}/purpur")
    return list(reversed(data.get("versions", [])))


async def get_fabric_versions() -> list[dict]:
    versions = await fetch_json(f"{FABRIC_META}/versions/game")
    return [{"id": v["version"], "stable": v["stable"]} for v in versions]


async def get_fabric_loader_versions() -> list[str]:
    loaders = await fetch_json(f"{FABRIC_META}/versions/loader")
    return [l["version"] for l in loaders]


async def get_fabric_installer_versions() -> list[str]:
    installers = await fetch_json(f"{FABRIC_META}/versions/installer")
    return [i["version"] for i in installers]


async def get_available_versions(core_type: str) -> list[dict]:
    try:
        if core_type == "vanilla":
            return await get_vanilla_versions()
        elif core_type == "paper":
            versions = await get_paper_versions()
            return [{"id": v, "type": "release"} for v in versions]
        elif core_type == "purpur":
            versions = await get_purpur_versions()
            return [{"id": v, "type": "release"} for v in versions]
        elif core_type == "fabric":
            return await get_fabric_versions()
        elif core_type == "forge":
            return await _get_forge_versions()
        elif core_type == "spigot":
            versions = await get_paper_versions()
            return [{"id": v, "type": "release"} for v in versions]
        return []
    except Exception as e:
        logger.error(f"Failed to fetch versions for {core_type}: {e}")
        return []


async def _get_forge_versions() -> list[dict]:
    try:
        url = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
        data = await fetch_json(url)
        versions = set()
        for key in data.get("promos", {}):
            mc_ver = key.rsplit("-", 1)[0]
            versions.add(mc_ver)
        return [{"id": v, "type": "release"} for v in sorted(versions, reverse=True)]
    except Exception:
        return [{"id": v, "type": "release"} for v in [
            "1.21.4", "1.21.3", "1.21.1", "1.20.6", "1.20.4", "1.20.2", "1.20.1",
            "1.19.4", "1.19.3", "1.19.2", "1.18.2", "1.17.1", "1.16.5"
        ]]


async def download_file(url: str, dest: Path, progress: DownloadProgress) -> Path:
    progress.status = "downloading"
    progress.filename = dest.name

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_ctx())) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            progress.total = int(resp.headers.get("Content-Length", 0))
            progress.downloaded = 0

            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)
                    progress.downloaded += len(chunk)

    progress.status = "completed"
    return dest


async def download_vanilla(version: str, dest_dir: Path, progress: DownloadProgress) -> Path:
    progress.status = "fetching_info"
    versions = await fetch_json(MOJANG_MANIFEST)
    ver_info = None
    for v in versions["versions"]:
        if v["id"] == version:
            ver_info = v
            break
    if not ver_info:
        raise ValueError(f"Vanilla version {version} not found")

    ver_data = await fetch_json(ver_info["url"])
    server_url = ver_data["downloads"]["server"]["url"]
    jar_name = f"server-{version}.jar"
    return await download_file(server_url, dest_dir / jar_name, progress)


async def download_paper(version: str, dest_dir: Path, progress: DownloadProgress) -> Path:
    progress.status = "fetching_info"
    builds = await get_paper_builds(version)
    if not builds:
        raise ValueError(f"No Paper builds for {version}")
    build = builds[-1]
    build_data = await fetch_json(
        f"{PAPER_API}/projects/paper/versions/{version}/builds/{build}"
    )
    download_name = build_data["downloads"]["application"]["name"]
    url = f"{PAPER_API}/projects/paper/versions/{version}/builds/{build}/downloads/{download_name}"
    return await download_file(url, dest_dir / download_name, progress)


async def download_purpur(version: str, dest_dir: Path, progress: DownloadProgress) -> Path:
    progress.status = "fetching_info"
    url = f"{PURPUR_API}/purpur/{version}/latest/download"
    jar_name = f"purpur-{version}.jar"
    return await download_file(url, dest_dir / jar_name, progress)


async def download_fabric(version: str, dest_dir: Path, progress: DownloadProgress) -> Path:
    progress.status = "fetching_info"
    loaders = await get_fabric_loader_versions()
    installers = await get_fabric_installer_versions()
    if not loaders or not installers:
        raise ValueError("Cannot fetch Fabric loader/installer versions")
    loader = loaders[0]
    installer = installers[0]
    url = f"{FABRIC_META}/versions/loader/{version}/{loader}/{installer}/server/jar"
    jar_name = f"fabric-server-{version}.jar"
    return await download_file(url, dest_dir / jar_name, progress)


async def download_forge(version: str, dest_dir: Path, progress: DownloadProgress) -> Path:
    progress.status = "fetching_info"
    promos = await fetch_json(
        "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
    )
    forge_ver = promos.get("promos", {}).get(f"{version}-recommended")
    if not forge_ver:
        forge_ver = promos.get("promos", {}).get(f"{version}-latest")
    if not forge_ver:
        raise ValueError(f"No Forge build for MC {version}")

    full_ver = f"{version}-{forge_ver}"
    url = (f"https://maven.minecraftforge.net/net/minecraftforge/forge/"
           f"{full_ver}/forge-{full_ver}-installer.jar")
    jar_name = f"forge-{full_ver}-installer.jar"
    installer_path = await download_file(url, dest_dir / jar_name, progress)

    progress.status = "installing_forge"
    import subprocess
    result = subprocess.run(
        ["java", "-jar", str(installer_path), "--installServer", str(dest_dir)],
        capture_output=True, text=True, cwd=str(dest_dir), timeout=300
    )
    if result.returncode != 0:
        logger.warning(f"Forge installer output: {result.stdout}\n{result.stderr}")

    for f in dest_dir.iterdir():
        if f.name.startswith("forge-") and f.name.endswith(".jar") and "installer" not in f.name:
            progress.status = "completed"
            return f

    run_sh = dest_dir / "run.sh"
    if run_sh.exists():
        progress.status = "completed"
        return installer_path

    progress.status = "completed"
    return installer_path


async def download_spigot(version: str, dest_dir: Path, progress: DownloadProgress) -> Path:
    progress.status = "fetching_info"
    jar_name = f"spigot-{version}.jar"
    url = f"{SPIGOT_DOWNLOAD}/spigot-{version}.jar"
    try:
        return await download_file(url, dest_dir / jar_name, progress)
    except Exception:
        progress.status = "building_spigot"
        build_tools_url = "https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar"
        bt_path = dest_dir / "BuildTools.jar"
        await download_file(build_tools_url, bt_path, progress)

        from app.java_manager import find_suitable_java_for_spigot, get_spigot_java_range
        java_path = find_suitable_java_for_spigot(version)
        if not java_path:
            min_j, max_j = get_spigot_java_range(version)
            raise RuntimeError(
                f"Spigot BuildTools для MC {version} требует Java {min_j}-{max_j}. "
                f"Подходящая версия Java не найдена. Установите нужную версию."
            )

        import subprocess
        progress.status = "building_spigot"
        result = subprocess.run(
            [java_path, "-jar", "BuildTools.jar", "--rev", version],
            capture_output=True, text=True, cwd=str(dest_dir), timeout=600
        )
        if result.returncode != 0:
            raise RuntimeError(f"Spigot build failed: {result.stderr[:500]}")

        for f in dest_dir.iterdir():
            if f.name.startswith("spigot-") and f.name.endswith(".jar"):
                return f
        raise RuntimeError("Spigot jar not found after build")


async def download_server(core_type: str, version: str, dest_dir: Path,
                          task_id: str) -> Path:
    progress = get_progress(task_id)
    try:
        downloaders = {
            "vanilla": download_vanilla,
            "paper": download_paper,
            "purpur": download_purpur,
            "fabric": download_fabric,
            "forge": download_forge,
            "spigot": download_spigot,
        }
        downloader = downloaders.get(core_type)
        if not downloader:
            raise ValueError(f"Unknown core type: {core_type}")
        return await downloader(version, dest_dir, progress)
    except Exception as e:
        progress.status = "error"
        progress.error = str(e)
        raise
