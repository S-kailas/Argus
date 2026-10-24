import asyncio
import logging
import time

import discord
from discord.ext import tasks

from config import (
    CPU_ALERT_PERCENT,
    RAM_ALERT_PERCENT,
    SWAP_ALERT_PERCENT,
    DISK_ALERT_PERCENT,
    RESOURCE_CHECK_INTERVAL_SECONDS,
    ALERT_COOLDOWN_SECONDS,
    ALERT_CHANNEL_ID,
)
from monitoring.resources import get_snapshot

log = logging.getLogger(__name__)


class ResourceAlertMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.last_sent = {}
        self.active_alerts = set()
        self.loop = tasks.loop(seconds=max(30, RESOURCE_CHECK_INTERVAL_SECONDS))(self._check)

    def start(self):
        if not self.loop.is_running():
            self.loop.start()

    def stop(self):
        if self.loop.is_running():
            self.loop.cancel()

    async def _check(self):
        if not ALERT_CHANNEL_ID:
            return
        try:
            data = await asyncio.to_thread(get_snapshot)
            checks = {
                "CPU": (data["cpu_percent"], CPU_ALERT_PERCENT, "%"),
                "RAM": (data["ram_percent"], RAM_ALERT_PERCENT, "%"),
                "Swap": (data["swap_percent"], SWAP_ALERT_PERCENT, "%"),
                "Root disk": (data["disk_percent"], DISK_ALERT_PERCENT, "%"),
            }
            channel = self.bot.get_channel(ALERT_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(ALERT_CHANNEL_ID)

            now = time.monotonic()
            for label, (value, threshold, unit) in checks.items():
                key = label.lower()
                if value >= threshold:
                    should_send = (
                        key not in self.active_alerts
                        or now - self.last_sent.get(key, 0) >= ALERT_COOLDOWN_SECONDS
                    )
                    self.active_alerts.add(key)
                    if should_send:
                        await channel.send(
                            f"⚠️ **HomeLab alert: {label} is high**\n"
                            f"Current: **{value:.1f}{unit}** · Threshold: **{threshold:.1f}{unit}**"
                        )
                        self.last_sent[key] = now
                elif key in self.active_alerts:
                    self.active_alerts.remove(key)
                    await channel.send(
                        f"✅ **HomeLab recovery: {label} is back below its threshold** "
                        f"(currently {value:.1f}{unit}; threshold {threshold:.1f}{unit})."
                    )
        except Exception:
            log.exception("Resource monitoring check failed")
