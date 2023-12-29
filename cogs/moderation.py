import discord
from discord.ext import commands
from strapbot import StrapBot
from core.context import StrapContext
from typing import Optional, Union
from datetime import datetime, timedelta
from core.utils import get_lang, StringOrTimeConverter
from .utils import Utilities


class Moderation(commands.Cog):
    """Commands to moderate your server."""

    emoji = "\N{shield}"

    def __init__(self, bot: StrapBot):
        self.bot = bot
        self.db = bot.get_cog_db(self)
        self.invite_url = Utilities.invite_url

    async def log(self, ctx: StrapContext, **kwargs):
        if ctx.guild == None:
            raise TypeError("this function can only be run in a guild")

        easteregg = kwargs.pop("easteregg", False)
        kwargs["reason"] = kwargs.get("reason", None) or ctx.format_message(
            "no_reason_provided", lang=ctx.guild_cog_lang
        )
        kwargs["moderator"] = (kwargs.pop("moderator", None) or ctx.author).mention
        timestamp = kwargs.pop("timestamp", None) or datetime.now()
        case = kwargs.pop("last_case", None)
        if not case:
            data = await self.db.find_one({"_id": ctx.guild.id}) or {}  # type: ignore
            case = data.get("last_case", "x")

        channel = ctx.guild.get_channel(
            ctx.guild_config.log_channel_id
        )  #  type: ignore
        if channel == None:
            return

        channel: Union[discord.TextChannel, discord.Thread] = channel

        ntitle = ": ".join(
            [
                ctx.format_message("case", {"n": case}, lang=ctx.guild_cog_lang),
                ctx.format_message("action_name", lang=ctx.guild_lang),
            ]
        )
        etitle = ctx.format_message("easteregg_embed_title", lang=ctx.guild_cog_lang)
        title = etitle if easteregg else ntitle
        color = discord.Color.red() if easteregg else ctx.me.accent_color
        embed = discord.Embed(color=color, timestamp=timestamp).set_author(
            name=title, icon_url=ctx.me.avatar
        )
        for k, v in kwargs.items():
            embed.add_field(name=k, value=v)

        if easteregg:
            rv = ctx.format_message(
                "reinvite_val",
                {"url": self.invite_url.format(ctx.me.id)},
                lang=ctx.guild_cog_lang,
            )
            embed.add_field(name="reinvite", value=rv)

        embed = ctx.format_embed(embed, lang=ctx.guild_cog_lang)
        await channel.send(embed=embed)

    async def warn_user(
        self, ctx: StrapContext, member: discord.Member, *, reason: Optional[str] = None
    ):
        """this is just a placeholder"""

    async def mute_user(
        self,
        ctx: StrapContext,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
        time: Optional[timedelta] = None,
    ):
        async def do_role_mute():
            role = ctx.guild.get_role(ctx.guild_config.muted_role_id)
            await member.add_roles(role, reason=reason)

        if time == None:
            await do_role_mute()
            return

        if ctx.guild_config.timeout:
            try:
                await member.timeout(time, reason=reason)
            except discord.errors.HTTPException:
                # Discord returns an error either if the timeout time is
                # longer than 28 days or the bot is trying to timeout
                # someone with admin permissions; if that's the case
                # then it'll be handled here with the muted role
                await do_role_mute()

            return

        await do_role_mute()

    async def unmute_user(
        self, ctx: StrapContext, member: discord.Member, *, reason: Optional[str] = None
    ):
        role = ctx.guild.get_role(ctx.guild_config.muted_role_id)
        await member.timeout(None, reason=reason)
        await member.remove_roles(role, reason=reason)

    async def kick_user(
        self, ctx: StrapContext, member: discord.Member, *, reason: Optional[str] = None
    ):
        await member.kick(reason=reason)

    async def ban_user(
        self,
        ctx: StrapContext,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
        time: Optional[timedelta] = None,
    ):
        # TODO: make a configuration for message delete seconds and days
        await member.ban(reason=reason, delete_message_days=0, delete_message_seconds=0)

    async def try_dm_user(
        self, ctx: StrapContext, member: discord.Member, *, reason: Optional[str] = None
    ):
        if not ctx.guild:
            return False

        config = await self.bot.get_config(member)
        lang = get_lang(config.lang, command=ctx.command)
        cog_lang = get_lang(config.lang, cog=self)

        reason = reason or ctx.format_message("no_reason_provided", lang=cog_lang)
        try:
            await member.send(
                ctx.format_message(
                    f"action_taken",
                    {"reason": reason, "guild": ctx.guild.name},
                    lang=lang,
                )
            )
        except Exception as e:
            code = 0
            if isinstance(e, discord.HTTPException):
                code = e.code

            if code == 50007:
                return False

            raise
        else:
            return True

    async def take_action(
        self, ctx: StrapContext, action: str, member: discord.Member, **kwargs
    ):
        allowed_mentions = discord.AllowedMentions(users=False)
        if not ctx.guild:
            raise Exception

        error = None
        dmed = True
        func = getattr(self, f"{action}_user", None)
        if func == None:
            raise KeyError(action)

        permact = f"{action}"
        if action in ["mute", "unmute"]:
            permact = "manage_roles"

        perms = ctx.channel.permissions_for(ctx.me)  # type: ignore
        perm = getattr(perms, permact, None)

        if perm != None and (perm or perms.administrator):
            if member.id == ctx.me.id:
                await self.log(ctx, easteregg=True, **kwargs)
                await ctx.send("easteregg", lang_to_use=ctx.cog_lang)
                await ctx.guild.leave()
                return

            if (
                member.roles[-1].position >= ctx.guild.me.roles[-1].position
                or member.id == ctx.guild.owner_id
            ):
                await ctx.send("higher_role")
                return

            await self.try_dm_user(ctx, member, reason=kwargs.get("reason", None))
            await func(ctx, member, **kwargs)
        elif perm != None:
            await ctx.send("bot_missing_perms")
            return
        elif member.id != ctx.me.id:
            # if it goes here, then it must be
            # because of warn or any placeholder
            # func that might have been added later
            try:
                dmed = await self.try_dm_user(
                    ctx, member, reason=kwargs.get("reason", None)
                )
            except Exception as e:
                error = e
        else:
            return

        message = "logged" + ("_error" if error else "")
        message = "success" if dmed and error == None else message
        await self.log(ctx, **kwargs)
        await ctx.send(
            message, member=member.mention, allowed_mentions=allowed_mentions
        )
        if error:
            raise error

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def warn(
        self, ctx: StrapContext, member: discord.Member, *, reason: Optional[str] = None
    ):
        async with ctx.typing():
            await self.take_action(ctx, "warn", member, reason=reason)

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def mute(
        self,
        ctx: StrapContext,
        member: discord.Member,
        time: Optional[StringOrTimeConverter] = None,
        *,
        reason: Optional[str] = None,
    ):
        if not ctx.guild.get_role(ctx.guild_config.muted_role_id):
            await ctx.send("not_configured")
            return

        reason = reason or ""
        if isinstance(time, str):
            reason = time + " " + reason
            time = None

        reason = reason.strip()
        if not reason:
            reason = None

        async with ctx.typing():
            await self.take_action(ctx, "mute", member, time=time, reason=reason)

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def unmute(
        self,
        ctx: StrapContext,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ):
        if not ctx.guild.get_role(ctx.guild_config.muted_role_id):
            await ctx.send("not_configured")
            return

        async with ctx.typing():
            await self.take_action(ctx, "unmute", member, reason=reason)

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def kick(
        self, ctx: StrapContext, member: discord.Member, *, reason: Optional[str] = None
    ):
        async with ctx.typing():
            await self.take_action(ctx, "kick", member, reason=reason)

    @commands.hybrid_command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: StrapContext,
        member: discord.Member,
        time: Optional[StringOrTimeConverter] = None,
        *,
        reason: Optional[str] = None,
    ):
        # TODO: actually implement auto-unban
        reason = reason or ""
        if isinstance(time, str):
            reason = time + " " + reason
            time = None

        reason = reason.strip()
        if not reason:
            reason = None

        async with ctx.typing():
            await self.take_action(ctx, "ban", member, time=time, reason=reason)


async def setup(bot: StrapBot):
    await bot.add_cog(Moderation(bot))
