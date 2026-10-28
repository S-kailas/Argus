import logging
import os

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, ALERT_CHANNEL_ID
from cogs.system import SystemCog #system cogs
from cogs.updates import UpdatesCog #update cogs
from cogs.temperature import TemperatureCog #temp cogs
from monitoring.alerts import ResourceAlertMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("homelab-bot")


class HomeLabBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.alert_channel_id = ALERT_CHANNEL_ID
        self.resource_monitor = ResourceAlertMonitor(self)

    async def setup_hook(self):
        await self.add_cog(SystemCog(self)) #system cogs
        await self.add_cog(UpdatesCog(self)) #update cog
        await self.add_cog(TemperatureCog(self))#temp cog
        self.resource_monitor.start()
        synced = await self.tree.sync()
        log.info("Synced %d application commands.", len(synced))
        
    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "?")

    async def close(self):
        self.resource_monitor.stop()
        await super().close()


bot = HomeLabBot()

#ping function removed from main


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing. Check your .env file.")
    bot.run(DISCORD_TOKEN, log_handler=None)
