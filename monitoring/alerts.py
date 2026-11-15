import asyncio
import logging
import time

import discord
from discord.ext import tasks

from config import (
    #resource-alert config
    CPU_ALERT_PERCENT,
    RAM_ALERT_PERCENT,
    SWAP_ALERT_PERCENT,
    DISK_ALERT_PERCENT,
    RESOURCE_CHECK_INTERVAL_SECONDS,
    ALERT_COOLDOWN_SECONDS,
    ALERT_CHANNEL_ID,
    #temperature-alert config
    TEMP_WARNING_C,
    TEMP_CRITICAL_C,
    TEMP_CHECK_INTERVAL_SECONDS,
    TEMP_ALERT_COOLDOWN_SECONDS,
)
from monitoring.resources import get_snapshot, get_top_processes
from monitoring.temperature import get_cpu_temperature

log = logging.getLogger(__name__)

#fetching top 2 Process(cpu)
async def get_top_cpu_processes_text() -> str:
    """Return the top two CPU-consuming processes."""

    try:
        processes = await asyncio.to_thread(
            get_top_processes, "cpu", 2
        )

        if not processes:
            return "\nTop CPU-consuming processes: unavailable."

        lines = []

        for process in processes:
            name = process["name"].replace("`", "'")[:25]

            lines.append(
                f"`{process['pid']}` **{name}** — "
                f"CPU: `{process['cpu_percent']:.1f}%`"
            )

        return (
            "\n\n**Top CPU-consuming processes:**\n"
            + "\n".join(lines)
        )

    except Exception:
        log.exception("Failed to collect top CPU processes")
        return "\nTop CPU-consuming processes: unavailable."

#Resource
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
            process_details = None

            for label, (value, threshold, unit) in checks.items():
                key = label.lower()
                if value >= threshold:
                    should_send = (
                        key not in self.active_alerts
                        or now - self.last_sent.get(key, 0) >= ALERT_COOLDOWN_SECONDS
                    )
                    self.active_alerts.add(key)
                    if should_send:
                        if process_details is None:
                             process_details = (await get_top_cpu_processes_text())

                        await channel.send(
                            f"⚠️ **HomeLab alert: {label} is high**\n"
                            f"Current: **{value:.1f}{unit}** · Threshold: **{threshold:.1f}{unit}**"
                            f"{process_details}"
                        )
                        self.last_sent[key] = now
                elif key in self.active_alerts:
                    self.active_alerts.remove(key)
                    await channel.send(
                        f"**HomeLab recovery: {label} is back below its threshold** "
                        f"(currently {value:.1f}{unit}; threshold {threshold:.1f}{unit})."
                    )
        except Exception:
            log.exception("Resource monitoring check failed")
#Temperature
class TemperatureAlertMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.previous_level = "normal"
        self.last_alert_time = 0.0

        self.loop = tasks.loop(
            seconds=max(10, TEMP_CHECK_INTERVAL_SECONDS)
        )(self._check)

    def start(self):
        if not self.loop.is_running():
            self.loop.start()

    def stop(self):
        if self.loop.is_running():
            self.loop.cancel()

    def temperature_level(self, temp: float) -> str:
        if temp >= TEMP_CRITICAL_C:
            return "critical"

        if temp >= TEMP_WARNING_C:
            return "warning"

        return "normal"

    async def _check(self):
        if not ALERT_CHANNEL_ID:
            return

        try:
            temp = await asyncio.to_thread(get_cpu_temperature)

            if temp is None:
                return

            level = self.temperature_level(temp)
            now = time.monotonic()

            channel = self.bot.get_channel(ALERT_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(ALERT_CHANNEL_ID)

            if level == "normal":
                if self.previous_level != "normal":
                    await channel.send(
                        f"**CPU temperature recovered:** {temp:.1f}°C"
                    )

                self.previous_level = "normal"
                self.last_alert_time = 0.0
                return

            level_changed = level != self.previous_level
            cooldown_elapsed = (
                now - self.last_alert_time >= TEMP_ALERT_COOLDOWN_SECONDS
            )

            if level_changed or cooldown_elapsed:
                process_details = await get_top_cpu_processes_text()

                await channel.send(
                    f"**CPU temperature {level.upper()}: "
                    f"{temp:.1f}°C**\n"
                    f"Warning: {TEMP_WARNING_C:.0f}°C | "
                    f"Critical: {TEMP_CRITICAL_C:.0f}°C"
                    f"{process_details}"
                )

                self.last_alert_time = now

            self.previous_level = level

        except Exception:
            log.exception("Temperature monitoring check failed")

