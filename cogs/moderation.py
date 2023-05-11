import discord
from discord.ext import commands
from strapbot import StrapBot


class Moderation(commands.Cog):
    """Commands to moderate your server."""

    emoji = "\N{shield}"

    def __init__(self, bot: StrapBot):
        self.bot = bot


async def setup(bot: StrapBot):
    await bot.add_cog(Moderation(bot))
