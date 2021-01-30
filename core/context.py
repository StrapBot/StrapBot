from logging import setLogRecordFactory
import json
import discord
from discord.ext import commands
from core.voice import VoiceState
from core.paginator import EmbedPaginatorSession
from core.languages import Language


class StrapContext(commands.Context):
    async def send(self, *msgs, **kwargs):
        reference = kwargs.pop("reference", self.message.to_reference())
        message = kwargs.pop("content", " ".join(str(msg) for msg in msgs))
        embeds = kwargs.pop("embeds", None)
        if embeds:
            session = EmbedPaginatorSession(self, *embeds)
            return await session.run()
        try:
            ret = await super().send(message, reference=reference, **kwargs)
        except discord.errors.HTTPException:
            ret = await super().send(message, **kwargs)

        return ret

    @property
    def voice_state(self):
        state = self.bot.voice_states.get(self.guild.id)
        if not state:
            state = VoiceState(self.bot, self)
            self.bot.voice_states[self.guild.id] = state

        return state

    async def get_lang(self, cls=None, *, cogs=False, cog=False, all=False):
        if cls == None:
            cls = self.command.cog

        cls = cls.__class__.__name__
        db = self.bot.db.db["LangConfig"]
        members = await db.find_one({"_id": "members"})
        guilds = await db.find_one({"_id": "guilds"})
        if str(self.author.id) in members:
            current = members[str(self.author.id)]["language"]
        elif str(self.guild.id) in guilds:
            current = guilds[str(self.guild.id)]["language"]
        else:
            current = self.bot.lang.default

        ret = json.load(open(f"core/languages/{current}.json"))

        if cogs:
            ret = ret["cogs"]
        elif cog:
            if cls == None:
                raise RuntimeError("No class specified.")

            ret = ret["cogs"][cls]
        elif all:
            ret = ret
        else:
            if cls == None:
                raise RuntimeError("No class specified.")
            ret = ret["cogs"][cls]["commands"][self.command.qualified_name]

        ret["current"] = current
        ret = Language(ret)
        return ret
