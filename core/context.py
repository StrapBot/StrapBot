import json
import discord
from discord.ext import commands


class Context(commands.Context):
    async def get_lang(self, cls=None, *, cogs=False, cog=False, all=False):
        if cls != None:
            cls = cls.__class__.__name__
        db = self.bot.db.db["LangConfig"]
        members = await db.find_one({"_id": "members"})
        guilds = await db.find_one({"_id": "guilds"})
        if str(self.author.id) in members:
            member = members[str(self.author.id)]
            ret = json.load(open(f"core/languages/{member['language']}.json"))
        elif str(self.guild.id) in guilds:
            guild = guilds[str(self.guild.id)]
            ret = json.load(open(f"core/languages/{guild['language']}.json"))
        else:
            ret = json.load(open(f"core/languages/{self.bot.lang.default}.json"))

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

        return ret
