import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
from cogs.system import owner_only #using owner verification function from system cogs
from monitoring.docker import (
    DockerCommandError, get_container_info, get_container_stats,
    get_containers, get_docker_summary,
)

log = logging.getLogger(__name__)


class DockerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _error(self, interaction, exc):
        log.warning("Docker command failed: %s", exc)
        msg = f"Docker monitoring failed: `{str(exc)[:900]}`"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="docker", description="Show Docker daemon and container summary.")
    @owner_only()
    async def docker(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            d = await asyncio.to_thread(get_docker_summary)
            e = discord.Embed(title="Docker Overview", color=discord.Color.blurple())
            for label, value in (
                ("Engine version", d["version"]), ("Containers", d["containers"]),
                ("Running", d["running"]), ("Paused", d["paused"]),
                ("Stopped", d["stopped"]), ("Images", d["images"]),
                ("Operating system", d["os"]), ("Storage driver", d["driver"]),
            ):
                e.add_field(name=label, value=str(value)[:1024], inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)
        except (DockerCommandError, ValueError) as exc:
            await self._error(interaction, exc)

    @app_commands.command(name="containers", description="List all Docker containers and their states.")
    @owner_only()
    async def containers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            rows = await asyncio.to_thread(get_containers)
            if not rows:
                await interaction.followup.send("No containers found.", ephemeral=True)
                return
            lines = []
            for r in rows[:25]:
                name = str(r.get("Names", "unnamed")).replace("`", "'")[:55]
                image = str(r.get("Image", "unknown")).replace("`", "'")[:65]
                lines.append(f"**{name}** · `{r.get('State', 'unknown')}`\n`{image}` — {str(r.get('Status', ''))[:90]}")
            e = discord.Embed(title=f"Docker Containers ({len(rows)})",
                              description="\n\n".join(lines)[:4000],
                              color=discord.Color.blurple())
            if len(rows) > 25:
                e.set_footer(text=f"Showing 25 of {len(rows)} containers.")
            await interaction.followup.send(embed=e, ephemeral=True)
        except (DockerCommandError, ValueError) as exc:
            await self._error(interaction, exc)

    @app_commands.command(name="docker_stats", description="Show live resource usage of running containers.")
    @owner_only()
    async def docker_stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            rows = await asyncio.to_thread(get_container_stats)
            if not rows:
                await interaction.followup.send("No running containers found.", ephemeral=True)
                return
            lines = []
            for r in rows[:20]:
                name = str(r.get("Name", r.get("ID", "unknown"))).replace("`", "'")[:45]
                lines.append(
                    f"**{name}**\nCPU `{r.get('CPUPerc', 'N/A')}` · "
                    f"RAM `{r.get('MemUsage', 'N/A')}` ({r.get('MemPerc', 'N/A')})\n"
                    f"Network `{r.get('NetIO', 'N/A')}`"
                )
            e = discord.Embed(title="Docker Container Statistics",
                              description="\n\n".join(lines)[:4000],
                              color=discord.Color.blurple())
            if len(rows) > 20:
                e.set_footer(text=f"Showing 20 of {len(rows)} running containers.")
            await interaction.followup.send(embed=e, ephemeral=True)
        except (DockerCommandError, ValueError) as exc:
            await self._error(interaction, exc)

    @app_commands.command(name="container_info", description="Show details for one container.")
    @app_commands.describe(container="Container name or ID")
    @owner_only()
    async def container_info(self, interaction: discord.Interaction, container: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            d = await asyncio.to_thread(get_container_info, container)
            e = discord.Embed(title=f"Container: {d['name']}", color=discord.Color.blurple())
            e.add_field(name="ID", value=d["id"] or "Unknown", inline=True)
            e.add_field(name="Status", value=d["status"], inline=True)
            e.add_field(name="Restart count", value=str(d["restarts"]), inline=True)
            e.add_field(name="Image", value=d["image"][:1024], inline=False)
            e.add_field(name="Started at", value=d["started"][:1024], inline=False)
            e.add_field(name="Ports", value="\n".join(d["ports"])[:1024] if d["ports"] else "None", inline=False)
            if d["status"] != "running":
                e.add_field(name="Exit code", value=str(d["exit_code"]), inline=True)
                e.add_field(name="Error", value=d["error"][:1024], inline=False)
            await interaction.followup.send(embed=e, ephemeral=True)
        except (DockerCommandError, ValueError) as exc:
            await self._error(interaction, exc)


async def setup(bot):
    await bot.add_cog(DockerCog(bot))
