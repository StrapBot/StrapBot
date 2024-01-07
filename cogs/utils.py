import discord
import math
import os
from discord.ext import commands
from core.help import StrapBotHelp
from core.context import StrapContext
from core.views import ConfigMenuView, ModChoiceView, YouTubeView
from datetime import datetime
from strapbot import StrapBot
from ipaddress import ip_address
from mcstatus import JavaServer, BedrockServer


def server_online():
    async def check(ctx: StrapContext) -> bool:
        ps = ctx.channel.permissions_for(ctx.author)  # type: ignore
        p = ps.administrator or ps.manage_guild
        return p and await ctx.bot.check_youtube_news()

    return commands.check(check)


class Utilities(commands.Cog):
    """Other uncategorized commands that could be useful."""

    emoji = "\N{hammer and wrench}"
    invite_url = "https://discord.com/oauth2/authorize?client_id={}&permissions=395945573431&scope=bot"

    def __init__(self, bot: StrapBot):
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
        async with ctx.typing():
            perms = ctx.channel.permissions_for(ctx.author)  # type: ignore
            if perms.administrator or perms.manage_guild:
                view = ModChoiceView(ctx)
                message = "mod_choice"
            else:
                view = ConfigMenuView(ctx, ctx.config)
                message = "choose_config"

            await ctx.send(
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
        url = self.invite_url.format(ctx.me.id)
        support = "https://discord.gg/G4de45Bywg"
        official = os.getenv("OFFICIAL", "0") == "1"
        await ctx.send(
            embed=discord.Embed(
                color=ctx.me.accent_color,
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

    @commands.hybrid_command()
    @server_online()
    async def youtube(self, ctx: StrapContext):
        async with ctx.typing():
            if not ctx.guild_config.yt_news_channel_id:
                await ctx.send("missing_config")
                return
            content = "main_menu"
            view = YouTubeView(ctx, content)
            await ctx.send(content, view=view)

    @commands.hybrid_command(aliases=["mcstatus", "mcstat", "mc"])
    async def minecraft(self, ctx: StrapContext, server: str):
        allow_local_ip = os.getenv("MCSTATUS_LOCAL_IP", "false").lower() in [
            "true",
            "1",
        ]
        if not allow_local_ip:
            host = server.lower().split(":")[0].split("/")[0]

            try:
                if host == "localhost" or ip_address(host).is_private:
                    await ctx.send("invalid")
                    return
            except ValueError:
                # it can't be a private IP
                pass

        srv = await JavaServer.async_lookup(server)
        bedrock = False
        try:
            status = await srv.async_status()
        except Exception:
            bedrock = True
            srv = await self.bot.loop.run_in_executor(
                None, BedrockServer.lookup, server
            )
            try:
                status = await srv.async_status()
            except Exception:
                # The server either doesn't exist or is offline
                await ctx.send("offline")
                return

        # remove formattings and colors
        clean_motd = "".join(
            part for part in status.motd.parsed if isinstance(part, str)
        )

        await ctx.send(
            f"{'bedrock_' if bedrock else ''}online",
            players=status.players.online,
            max_players=status.players.max,
            motd=clean_motd,
        )


async def setup(bot: StrapBot):
    await bot.add_cog(Utilities(bot))
