import json
import discord
import typing
from discord.ext import commands
from lavalink.models import BasePlayer, DefaultPlayer
from core.paginator import EmbedPaginatorSession, MessagePaginatorSession
from core.languages import Language
from discord_slash import SlashContext


class StrapCTX:
    message: discord.Message
    guild: discord.Guild
    author: discord.Member
    lang: Language = None

    async def send(self, *msgs, **kwargs) -> discord.Message:
        reference = None
        if not self.is_slash:
            reference = self.message.reference or self.message.to_reference()
        kwargs["reference"] = reference = kwargs.pop("reference", reference)
        message = kwargs.pop("content", " ".join(str(msg) for msg in msgs))
        embeds = kwargs.pop("embeds", None)
        messages = kwargs.pop("messages", None)
        hidden = kwargs.get("hidden", False)
        if embeds:
            session = EmbedPaginatorSession(self, *embeds)
            return await session.run()
        elif messages:
            embed = kwargs.pop("embed", None)
            session = MessagePaginatorSession(self, *messages, embed=embed)
            return await session.run()
        if hidden and not self.is_slash:
            try:
                ret = await self.author.send(message, **kwargs)
            except (discord.errors.HTTPException, discord.errors.Forbidden):
                await super().send(
                    embed=discord.Embed(
                        description="Please make sure you have DMs enabled.",
                        color=discord.Color.red(),
                    ).set_author(name="Error", icon_url=self.me.avatar_url),
                    **kwargs,
                )
                raise
        else:
            send = super().send
            if not self.is_slash:
                kwargs.pop("hidden", False)
                _defercoso = False
                if self.deferred != None and not self.defer_edited:
                    send = self.deferred.edit
                    try:
                        del kwargs["content"]
                    except Exception:
                        pass
                    self.defer_edited = True
                    _defercoso = True
                    kwargs.pop("reference")
            else:
                kwargs.pop("reference")

            ret = await send(content=message, **kwargs)
            if not self.is_slash and self.deferred and _defercoso:
                ret = self.deferred

        return ret

    @property
    def player(self) -> typing.Union[BasePlayer, DefaultPlayer]:
        ret = self.bot.lavalink.player_manager.get(self.guild.id)

        return ret

    async def get_lang(self, cls=None, *, cogs=False, cog=False, all=False) -> Language:
        if cls == None:
            cls = self.cog

        if self.is_slash:
            command_name = self.command
        else:
            command_name = self.command.qualified_name

        cls = cls.__class__.__name__

        current = await self.bot.config.get(
            self.author.id,
            "lang",
            await self.bot.config.get(self.guild.id, "lang", self.bot.lang.default),
        )

        ret = json.load(open(f"core/languages/{current}.json"))

        if cogs:
            ret = ret.get("cogs", {})
        elif cog:
            if cls == None:
                raise RuntimeError("No class specified.")

            ret = ret.get("cogs", {}).get(cls, {})
        elif all:
            ret = ret
        else:
            if cls == None:
                raise RuntimeError("No class specified.")
            ret = (
                ret.get("cogs", {})
                .get(cls, {})
                .get("commands", {})
                .get(command_name, {})
            )

        ret["current"] = current
        ret["_default_"] = self.bot.lang.default
        ret = Language(ret)
        return ret

    async def defer(self, *args, **kwargs: dict):
        msg = kwargs.pop("message", "Please wait...")
        if self.is_slash:
            return await super().defer(*args, **kwargs)
        elif self.deferred:
            raise RuntimeError("Can't defer more than once")
        else:
            self.deferred = await self.send(msg)
            return self.deferred


class StrapContext(StrapCTX, commands.Context):
    is_slash = False
    defer_edited = False
    deferred = None


class StrapSlashContext(StrapCTX, SlashContext):
    is_slash = True
