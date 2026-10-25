#/temparature is defined here
import os
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from monitoring.temperature import get_temperatures, get_cpu_temperature

#Importing env variables from config 
from config import (
    TEMP_WARNING_C,
    TEMP_CRITICAL_C,
    TEMP_CHECK_INTERVAL_SECONDS,
    TEMP_ALERT_COOLDOWN_SECONDS,
)

WARNING_C = TEMP_WARNING_C
CRITICAL_C = TEMP_CRITICAL_C
CHECK_INTERVAL = TEMP_CHECK_INTERVAL_SECONDS
ALERT_COOLDOWN = TEMP_ALERT_COOLDOWN_SECONDS

previous_level = "normal"
last_alert_time = 0.0


def temperature_level(temp: float) -> str:
    if temp >= CRITICAL_C:
        return "critical"
    if temp >= WARNING_C:
        return "warning"
    return "normal"


class TemperatureCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.alert_channel_id = int(
            os.getenv("ALERT_CHANNEL_ID", "0")
        )

    async def cog_load(self):
        self.temperature_monitor.start()

    async def cog_unload(self):
        self.temperature_monitor.cancel()

    @app_commands.command(
        name="temperature",
        description="Show current CPU temperature readings"
    )
    async def temperature(self, interaction: discord.Interaction):
        readings = get_temperatures()

        if not readings:
            await interaction.response.send_message(
                "No CPU temperature sensors were detected.",
                ephemeral=True,
            )
            return

        lines = [
            f"**{label}:** {temp:.1f}°C"
            for label, temp in sorted(readings.items())
        ]

        cpu_temp = get_cpu_temperature()
        if cpu_temp is not None:
            lines.append(f"\n**Monitored CPU temperature:** {cpu_temp:.1f}°C")

        await interaction.response.send_message(
            "\n".join(lines),
            ephemeral=True,
        )

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def temperature_monitor(self):
        global previous_level, last_alert_time

        temp = get_cpu_temperature()
        if temp is None:
            return

        level = temperature_level(temp)
        now = time.monotonic()

        if level == "normal":
            if previous_level != "normal":
                await self.send_alert(
                    f" **CPU temperature recovered:** {temp:.1f}°C"
                )
            previous_level = "normal"
            last_alert_time = 0.0
            return

        # Alert on a level change, or repeat after the cooldown.
        level_changed = level != previous_level
        cooldown_elapsed = now - last_alert_time >= ALERT_COOLDOWN

        if level_changed or cooldown_elapsed:
            emoji = "" if level == "critical" else ""
            await self.send_alert(
                f"{emoji} **CPU temperature {level.upper()}: "
                f"{temp:.1f}°C**\n"
                f"Warning: {WARNING_C:.0f}°C | "
                f"Critical: {CRITICAL_C:.0f}°C"
            )
            last_alert_time = now

        previous_level = level

    @temperature_monitor.before_loop
    async def before_temperature_monitor(self):
        await self.bot.wait_until_ready()

    async def send_alert(self, message: str):
        if not self.alert_channel_id:
            return

        channel = self.bot.get_channel(self.alert_channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(
                    self.alert_channel_id
                )
            except (discord.HTTPException, discord.Forbidden):
                return

        if hasattr(channel, "send"):
            try:
                await channel.send(message)
            except (discord.HTTPException, discord.Forbidden):
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TemperatureCog(bot))

