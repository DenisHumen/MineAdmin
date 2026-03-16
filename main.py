#!/usr/bin/env python3

import sys
import os
import logging
import platform
import importlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VERSION_FILE = BASE_DIR / "VERSION"


def get_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "unknown"


def setup_logging():
    log_dir = BASE_DIR / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "mineadmin.log", encoding="utf-8"),
        ],
    )


def check_python_version():
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        print(f"[ERROR] Python 3.10+ required, found {major}.{minor}")
        print("  Download: https://www.python.org/downloads/")
        sys.exit(1)
    return f"{major}.{minor}.{sys.version_info[2]}"


def check_dependencies() -> list[str]:
    # When running as a PyInstaller bundle all packages are already included
    if getattr(sys, "frozen", False):
        return []
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "sqlalchemy": "sqlalchemy",
        "aiosqlite": "aiosqlite",
        "aiohttp": "aiohttp",
        "aiofiles": "aiofiles",
        "bcrypt": "bcrypt",
        "jwt": "pyjwt",
        "psutil": "psutil",
        "jinja2": "jinja2",
        "multipart": "python-multipart",
        "websockets": "websockets",
        "certifi": "certifi",
        "paramiko": "paramiko",
    }
    missing = []
    for module, pip_name in required.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)
    return missing


def check_data_dirs():
    from app.config import ensure_dirs
    ensure_dirs()


def print_banner(version: str, python_ver: str, host: str, port: int):
    from app.network_checker import get_local_ip
    local_ip = get_local_ip()

    print()
    print("=" * 58)
    print("   __  __ _              _       _           _       ")
    print("  |  \\/  (_)_ __   ___  / \\   __| |_ __ ___ (_)_ __  ")
    print("  | |\\/| | | '_ \\ / _ \\/  _\\ / _` | '_ ` _ \\| | '_ \\ ")
    print("  | |  | | | | | |  __/ (_| | (_| | | | | | | | | | |")
    print("  |_|  |_|_|_| |_|\\___|\\___|\\__,_|_| |_| |_|_|_| |_|")
    print()
    print(f"  Version:  {version}")
    print(f"  Python:   {python_ver}")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print()
    print(f"  Web UI:   http://{local_ip}:{port}")
    print(f"  Local:    http://127.0.0.1:{port}")
    print()
    print("=" * 58)
    print()


def main():
    version = get_version()
    python_ver = check_python_version()

    setup_logging()
    logger = logging.getLogger("mineadmin")

    print(f"\n  MineAdmin v{version} starting...")
    print(f"  Checking dependencies...\n")

    missing = check_dependencies()
    if missing:
        print("[ERROR] Missing Python packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\n  Install with: pip install {' '.join(missing)}")
        print(f"  Or run:       pip install -r requirements.txt\n")
        sys.exit(1)

    print("  [OK] All dependencies installed")

    check_data_dirs()
    print("  [OK] Data directories ready")

    from app.config import load_config
    cfg = load_config()
    print("  [OK] Configuration loaded")

    host = cfg["web"]["host"]
    port = cfg["web"]["port"]

    print_banner(version, python_ver, host, port)

    import uvicorn
    from app.webapp import create_app

    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
