import json
import discord
import typing
from discord.ext import commands
from lavalink.models import BasePlayer, DefaultPlayer
from core.paginator import EmbedPaginatorSession, MessagePaginatorSession
from core.languages import Language


class StrapContext(commands.Context):
    message: discord.Message
    guild: discord.Guild
    author: discord.Member
    lang: Language = None

    async def send(self, *msgs, **kwargs) -> discord.Message:
        reference = self.message.reference or self.message.to_reference()
        reference = kwargs.pop("reference", reference)
        message = kwargs.pop("content", " ".join(str(msg) for msg in msgs))
        embeds = kwargs.pop("embeds", None)
        messages = kwargs.pop("messages", None)
        if embeds:
            session = EmbedPaginatorSession(self, *embeds)
            return await session.run()
        elif messages:
            embed = kwargs.pop("embed", None)
            session = MessagePaginatorSession(self, *messages, embed=embed)
            return await session.run()
        try:
            ret = await super().send(message, reference=reference, **kwargs)
        except discord.errors.HTTPException:
            ret = await super().send(message, **kwargs)

        return ret

    @property
    def player(self) -> typing.Union[BasePlayer, DefaultPlayer]:
        ret = self.bot.lavalink.player_manager.get(self.guild.id)

        return ret

    async def get_lang(self, cls=None, *, cogs=False, cog=False, all=False) -> Language:
        if cls == None:
            cls = self.command.cog

        cls = cls.__class__.__name__
        db = self.bot.db.db["Config"]
        members = await db.find_one({"_id": "members"})
        guilds = await db.find_one({"_id": "guilds"})
        if str(self.author.id) in members:
            current = members[str(self.author.id)].get(
                "language", self.bot.lang.default
            )
        elif str(self.guild.id) in guilds:
            current = guilds[str(self.guild.id)].get("language", self.bot.lang.default)
        else:
            current = self.bot.lang.default

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
                .get(self.command.qualified_name, {})
            )

        ret["current"] = current
        ret = Language(ret)
        return ret
