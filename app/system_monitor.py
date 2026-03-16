import psutil
import platform
import os
from typing import Optional
from pathlib import Path


def _get_cpu_model() -> str:
    name = platform.processor()
    if name:
        return name
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (OSError, IndexError):
        pass
    try:
        import subprocess
        r = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "Model name" in line or "Имя модели" in line:
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.machine()


def get_system_info() -> dict:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": _get_cpu_model(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "total_ram_bytes": mem.total,
        "total_disk_bytes": disk.total,
    }


def get_all_disks(servers_path: str = None) -> list[dict]:
    disks = []
    if servers_path is None:
        from app.config import SERVERS_DIR
        servers_path = str(SERVERS_DIR)

    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        is_main = False
        try:
            is_main = os.path.commonpath([os.path.realpath(servers_path), os.path.realpath(part.mountpoint)]) == os.path.realpath(part.mountpoint)
        except ValueError:
            pass
        disks.append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
            "is_main": is_main,
        })

    main_disks = [d for d in disks if d["is_main"]]
    if len(main_disks) > 1:
        best = max(main_disks, key=lambda d: len(d["mountpoint"]))
        for d in disks:
            d["is_main"] = (d["mountpoint"] == best["mountpoint"])

    disks.sort(key=lambda d: (not d["is_main"], d["mountpoint"]))
    return disks


def get_system_stats() -> dict:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)

    net = psutil.net_io_counters()

    all_disks = get_all_disks()
    main_disk = next((d for d in all_disks if d["is_main"]), None)
    if main_disk:
        disk_data = {
            "total": main_disk["total"],
            "used": main_disk["used"],
            "free": main_disk["free"],
            "percent": main_disk["percent"],
        }
    else:
        disk_data = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        }

    return {
        "cpu": {
            "percent": cpu_percent,
            "per_core": cpu_per_core,
            "count": psutil.cpu_count(),
        },
        "memory": {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
        },
        "disk": disk_data,
        "disks": all_disks,
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
        },
    }


def get_process_stats(pid: int) -> Optional[dict]:
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            mem = proc.memory_info()
            cpu = proc.cpu_percent(interval=0.1)
            return {
                "pid": pid,
                "cpu_percent": cpu,
                "memory_rss": mem.rss,
                "memory_vms": mem.vms,
                "status": proc.status(),
                "threads": proc.num_threads(),
                "create_time": proc.create_time(),
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_java_processes() -> list[dict]:
    result = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent", "memory_info"]):
        try:
            name = proc.info["name"] or ""
            cmdline = proc.info.get("cmdline") or []
            if "java" in name.lower() or any("java" in c.lower() for c in cmdline):
                mem = proc.info.get("memory_info")
                result.append({
                    "pid": proc.info["pid"],
                    "name": name,
                    "cmdline": " ".join(cmdline[:5]),
                    "cpu_percent": proc.info.get("cpu_percent", 0),
                    "memory_rss": mem.rss if mem else 0,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def format_bytes(size: int) -> dict:
    return {
        "bytes": size,
        "kb": round(size / 1024, 2),
        "mb": round(size / (1024 ** 2), 2),
        "gb": round(size / (1024 ** 3), 2),
        "tb": round(size / (1024 ** 4), 6),
        "bits": size * 8,
        "human": _human_readable(size),
    }


def _human_readable(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
