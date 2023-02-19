import discord
from discord.ext import commands


class Moderation(commands.Cog):
    """Commands to moderate your server."""

    def __init__(self, bot):
        from strapbot import StrapBot

        self.bot: StrapBot = bot


async def setup(bot):
    await bot.add_cog(Moderation(bot))
