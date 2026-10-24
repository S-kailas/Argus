import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from monitoring.resources import get_snapshot, get_top_processes, format_bytes


def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == OWNER_ID:
            return True
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "You are not authorized to use this command.", ephemeral=True
            )
        return False
    return app_commands.check(predicate)


class SystemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Show current server resource usage.")
    @owner_only()
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await __import__("asyncio").to_thread(get_snapshot)
        embed = discord.Embed(title="HomeLab Server Status", color=discord.Color.blurple())
        embed.add_field(name="CPU", value=f"{data['cpu_percent']:.1f}%", inline=True)
        embed.add_field(name="RAM", value=f"{data['ram_percent']:.1f}% ({format_bytes(data['ram_used'])} / {format_bytes(data['ram_total'])})", inline=True)
        embed.add_field(name="Swap", value=f"{data['swap_percent']:.1f}%", inline=True)
        embed.add_field(name="Root disk", value=f"{data['disk_percent']:.1f}% ({format_bytes(data['disk_used'])} / {format_bytes(data['disk_total'])})", inline=True)
        embed.add_field(name="Load average", value=data["load_average"], inline=True)
        embed.add_field(name="Uptime", value=data["uptime"], inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="processes", description="List processes using the most CPU or memory.")
    @app_commands.describe(sort_by="Choose whether to rank processes by CPU or memory.")
    @app_commands.choices(sort_by=[
        app_commands.Choice(name="CPU", value="cpu"),
        app_commands.Choice(name="Memory", value="memory"),
    ])
    @owner_only()
    async def processes(self, interaction: discord.Interaction, sort_by: app_commands.Choice[str] = None):
        await interaction.response.defer(ephemeral=True, thinking=True)
        key = sort_by.value if sort_by else "memory"
        rows = await __import__("asyncio").to_thread(get_top_processes, key, 10)
        if not rows:
            await interaction.followup.send("No process information was available.", ephemeral=True)
            return
        lines = []
        for p in rows:
            name = p["name"].replace("`", "'")[:28]
            lines.append(
                f"`{p['pid']:>6}` **{name}** — CPU `{p['cpu_percent']:.1f}%`, RAM `{p['memory_percent']:.1f}%`"
            )
        embed = discord.Embed(
            title=f"Top processes by {key.upper()}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="uptime", description="Show how long the server has been running.")
    @owner_only()
    async def uptime(self, interaction: discord.Interaction):
        import asyncio
        data = await asyncio.to_thread(get_snapshot)
        await interaction.response.send_message(f"Server uptime: **{data['uptime']}**", ephemeral=True)

    @app_commands.command(name="help", description="List available HomeLab bot commands.")
    @owner_only()
    async def help_command(self, interaction: discord.Interaction):
        text = (
            "**HomeLab bot commands**\n"
            "`/ping` — check bot responsiveness\n"
            "`/status` — CPU, RAM, swap, disk, load and uptime\n"
            "`/processes` — top processes by CPU or memory\n"
            "`/uptime` — server uptime\n"
            "`/help` — this command"
        )
        await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
