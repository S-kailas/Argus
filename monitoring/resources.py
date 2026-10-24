import os
import time
from datetime import timedelta

import psutil

from config import DISK_PATH


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def get_snapshot() -> dict:
    # interval=1 gives a more meaningful CPU sample; this runs in a worker thread.
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage(DISK_PATH)
    try:
        load_average = ", ".join(f"{n:.2f}" for n in os.getloadavg())
    except (AttributeError, OSError):
        load_average = "Unavailable"

    return {
        "cpu_percent": cpu_percent,
        "ram_percent": memory.percent,
        "ram_used": memory.used,
        "ram_total": memory.total,
        "swap_percent": swap.percent,
        "swap_used": swap.used,
        "swap_total": swap.total,
        "disk_percent": disk.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "load_average": load_average,
        "uptime": _format_duration(time.time() - psutil.boot_time()),
    }


def get_top_processes(sort_by: str = "memory", limit: int = 10) -> list[dict]:
    rows = []
    # Prime CPU counters, then sample without blocking the event loop (caller uses a worker).
    for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            proc.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.25)
    for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            rows.append({
                "pid": proc.info["pid"],
                "name": proc.info.get("name") or "unknown",
                "memory_percent": float(proc.info.get("memory_percent") or 0.0),
                "cpu_percent": float(proc.cpu_percent(None)),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    return sorted(rows, key=lambda row: row[key], reverse=True)[:max(1, min(limit, 20))]
