import discord
import math
import os
import json
from discord.ext import commands
from core.help import StrapBotHelp
from core.context import StrapContext
from core.views import ConfigMenuView, ModChoiceView
from datetime import datetime

def server_online():
    async def check(ctx: StrapContext) -> bool:
        return await ctx.bot.check_youtube_news()

    return commands.check(check)

class Utilities(commands.Cog):
    """Other uncategorized commands that could be useful."""

    emoji = "\N{hammer and wrench}"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = StrapBotHelp()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @staticmethod
    def truncate(num) -> float:
        return math.floor(num * 10**3) / 10**3

    @commands.hybrid_command()
    async def config(self, ctx: StrapContext):
        """Change the bot's settings."""
        await ctx.defer()
        perms = ctx.channel.permissions_for(ctx.author)  # type: ignore
        if perms.administrator or perms.manage_guild:
            view = ModChoiceView(ctx)
            message = "mod_choice"
        else:
            view = ConfigMenuView(ctx, ctx.config)
            message = "choose_config"

        await ctx.reply(
            message,
            view=view,
        )

    @commands.hybrid_command()
    async def ping(self, ctx: StrapContext):
        """Checks the websocket latency."""
        # I prefer truncating the number instead of rounding it
        wslatency = "---.---"
        reqlatency = "---.---"

        message = lambda: ctx.format_message(
            "pong", dict(websocket_latency=wslatency, request_latency=reqlatency)
        )
        before = datetime.now()
        msg = await ctx.send(message())
        after = datetime.now()
        wslatency = str(self.truncate(self.bot.ws.latency * 1000))
        reqlatency = str(self.truncate((after - before).total_seconds() * 1000))
        await msg.edit(content=message())

    @commands.hybrid_command()
    async def invite(self, ctx: StrapContext):
        """Invite me to your server!"""
        url = f"https://discord.com/oauth2/authorize?client_id={ctx.me.id}&permissions=395945573431&scope=bot"
        support = "https://discord.gg/G4de45Bywg"
        official = os.getenv("OFFICIAL", "0") == "1"
        await ctx.send(
            embed=discord.Embed(
                color=discord.Color.lighter_grey(),
                description="support_link" if official else "link",
            )
            .set_author(
                name="title",
                icon_url=ctx.me.avatar,
            )
            .set_footer(text="footer", icon_url=ctx.me.avatar),
            invite_link=url,
            support_guild_link=support,
            ephemeral=True,
        )

    @commands.command()
    @server_online()
    async def youtube(self, ctx: StrapContext):
        await ctx.send("test")



async def setup(bot):
    await bot.add_cog(Utilities(bot))
