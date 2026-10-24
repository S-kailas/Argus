"""Discord commands and scheduled notifications for Debian update detection."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import OWNER_ID, ALERT_CHANNEL_ID
from services.apt import check_updates, format_update_result

log = logging.getLogger(__name__)

UPDATE_CHECK_INTERVAL_HOURS = 12


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


class UpdatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_notified_signature: tuple[str, ...] | None = None
        self.scheduled_check.start()

    def cog_unload(self):
        self.scheduled_check.cancel()

    async def _send_to_alert_channel(self, message: str):
        if not ALERT_CHANNEL_ID:
            log.warning("ALERT_CHANNEL_ID is not configured; cannot send update notification.")
            return
        channel = self.bot.get_channel(ALERT_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ALERT_CHANNEL_ID)
            except discord.DiscordException:
                log.exception("Could not fetch configured alert channel.")
                return
        try:
            await channel.send(message)
        except discord.DiscordException:
            log.exception("Could not send update notification.")

    async def _perform_check(self, notify_on_updates: bool) -> str:
        result = await check_updates()
        message = format_update_result(result)
        if not result.success:
            await self._send_to_alert_channel("⚠️ " + message)
            return message

        if result.total_count == 0:
            self.last_notified_signature = None
            return message

        signature = tuple(result.packages) + (str(result.total_count),)
        if notify_on_updates and signature != self.last_notified_signature:
            self.last_notified_signature = signature
            await self._send_to_alert_channel("🔔 **Updates are available**\n" + message)
        return message

    @tasks.loop(hours=UPDATE_CHECK_INTERVAL_HOURS)
    async def scheduled_check(self):
        await self._perform_check(notify_on_updates=True)

    @scheduled_check.before_loop
    async def before_scheduled_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="updates",
        description="Check Debian for available updates (does not install them).",
    )
    @owner_only()
    async def updates(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await self._perform_check(notify_on_updates=False)
        # Discord message limit is 2000 chars; the formatted response is bounded below.
        await interaction.followup.send(message[:1900], ephemeral=True)

    @app_commands.command(
        name="updatecheck",
        description="Refresh APT metadata and check for updates now; installs nothing.",
    )
    @owner_only()
    async def updatecheck(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await self._perform_check(notify_on_updates=True)
        await interaction.followup.send(message[:1900], ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(UpdatesCog(bot))
