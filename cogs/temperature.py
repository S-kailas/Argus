#/temparature is defined here
import discord
from discord import app_commands
from discord.ext import commands

from monitoring.temperature import get_temperatures, get_cpu_temperature

class TemperatureCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

