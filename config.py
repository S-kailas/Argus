import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
ALERT_CHANNEL_ID_RAW = os.getenv("ALERT_CHANNEL_ID", "").strip()

if not OWNER_ID_RAW.isdigit():
    raise RuntimeError("OWNER_ID must be your numeric Discord user ID.")
OWNER_ID = int(OWNER_ID_RAW)

ALERT_CHANNEL_ID = int(ALERT_CHANNEL_ID_RAW) if ALERT_CHANNEL_ID_RAW.isdigit() else None

CPU_ALERT_PERCENT = float(os.getenv("CPU_ALERT_PERCENT", "90"))
RAM_ALERT_PERCENT = float(os.getenv("RAM_ALERT_PERCENT", "90"))
SWAP_ALERT_PERCENT = float(os.getenv("SWAP_ALERT_PERCENT", "80"))
DISK_ALERT_PERCENT = float(os.getenv("DISK_ALERT_PERCENT", "90"))
RESOURCE_CHECK_INTERVAL_SECONDS = int(os.getenv("RESOURCE_CHECK_INTERVAL_SECONDS", "60"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "900"))

TEMP_WARNING_C = float(os.getenv("TEMP_WARNING_C", "80"))
TEMP_CRITICAL_C = float(os.getenv("TEMP_CRITICAL_C", "90"))
TEMP_CHECK_INTERVAL_SECONDS = int(os.getenv("TEMP_CHECK_INTERVAL_SECONDS", "60"))
TEMP_ALERT_COOLDOWN_SECONDS = int(os.getenv("TEMP_ALERT_COOLDOWN_SECONDS", "900"))
DISK_PATH = os.getenv("DISK_PATH", "/")
