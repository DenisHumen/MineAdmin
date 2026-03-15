import os
import shutil
from pathlib import Path
from typing import Optional
from app.system_monitor import format_bytes


def list_directory(base_dir: Path, relative_path: str = "") -> list[dict]:
    target = (base_dir / relative_path).resolve()

    if not str(target).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")

    if not target.exists():
        return []

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            stat = entry.stat()
            rel = str(entry.relative_to(base_dir))
            item = {
                "name": entry.name,
                "path": rel,
                "is_dir": entry.is_dir(),
                "size": format_bytes(stat.st_size) if not entry.is_dir() else None,
                "modified": stat.st_mtime,
                "extension": entry.suffix.lower() if entry.is_file() else None,
            }
            if entry.is_dir():
                try:
                    item["children_count"] = sum(1 for _ in entry.iterdir())
                except PermissionError:
                    item["children_count"] = 0
            items.append(item)
    except PermissionError:
        raise PermissionError(f"Cannot read directory: {relative_path}")

    return items


def read_text_file(base_dir: Path, relative_path: str, max_size: int = 5 * 1024 * 1024) -> dict:
    target = (base_dir / relative_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")
    if not target.exists():
        raise FileNotFoundError(f"File not found: {relative_path}")

    stat = target.stat()
    if stat.st_size > max_size:
        raise ValueError(f"File too large: {stat.st_size} bytes (max {max_size})")

    text_extensions = {".txt", ".log", ".properties", ".yml", ".yaml", ".json",
                       ".cfg", ".conf", ".ini", ".toml", ".xml", ".csv", ".md",
                       ".sh", ".bat", ".cmd", ".py", ".js", ".html", ".css"}

    ext = target.suffix.lower()
    if ext not in text_extensions:
        raise ValueError(f"Not a supported text file: {ext}")

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "name": target.name,
        "path": relative_path,
        "content": content,
        "size": format_bytes(stat.st_size),
        "extension": ext,
    }


def save_text_file(base_dir: Path, relative_path: str, content: str):
    target = (base_dir / relative_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def delete_path(base_dir: Path, relative_path: str):
    target = (base_dir / relative_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")
    if not target.exists():
        raise FileNotFoundError(f"Not found: {relative_path}")

    if target == base_dir.resolve():
        raise PermissionError("Cannot delete server root directory")

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def create_directory(base_dir: Path, relative_path: str):
    target = (base_dir / relative_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")
    target.mkdir(parents=True, exist_ok=True)


def rename_path(base_dir: Path, relative_path: str, new_name: str):
    target = (base_dir / relative_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")
    if not target.exists():
        raise FileNotFoundError(f"Not found: {relative_path}")
    new_path = target.parent / new_name
    if not str(new_path).startswith(str(base_dir.resolve())):
        raise PermissionError("Access denied: path traversal detected")
    target.rename(new_path)


def get_directory_size(path: Path) -> int:
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except PermissionError:
        pass
    return total
