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

async def setup(bot: commands.Bot):
    await bot.add_cog(TemperatureCog(bot))

