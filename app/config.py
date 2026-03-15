import os
import json
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SERVERS_DIR = DATA_DIR / "servers"
DB_DIR = DATA_DIR / "db"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "db_type": "sqlite",
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "mineadmin"
    },
    "web": {
        "host": "0.0.0.0",
        "port": 8080
    },
    "secret_key": secrets.token_hex(32),
    "default_java_memory": "2G",
    "max_java_memory": "4G",
    "ssh": {
        "enabled": False,
        "host": "localhost",
        "port": 22,
        "username": "",
        "auth_type": "password",
        "password": "",
        "key_path": "",
    },
}


def ensure_dirs():
    for d in [DATA_DIR, SERVERS_DIR, DB_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_sqlite_url() -> str:
    return f"sqlite+aiosqlite:///{DB_DIR / 'mineadmin.db'}"


def get_mysql_url(cfg: dict) -> str:
    m = cfg["mysql"]
    return f"mysql+aiomysql://{m['user']}:{m['password']}@{m['host']}:{m['port']}/{m['database']}"
