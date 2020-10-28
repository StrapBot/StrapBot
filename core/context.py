import json
import discord
from discord.ext import commands

class Context(commands.Context):
    async def get_lang(self, cog):
        cog = cog.__class__.__name__
        db = self.bot.db.db["LangConfig"]
        members = await db.find_one({"_id": "members"})
        guilds = await db.find_one({"_id": "guilds"})
        if str(self.author.id) in members:
            member = members[str(self.author.id)]
            ret = json.load(open(f"core/languages/{member['language']}.json"))["cogs"][cog]
        elif str(self.guild.id) in guilds:
            guild = guilds[str(self.guild.id)]
            ret = json.load(open(f"core/languages/{guild['language']}.json"))["cogs"][cog]
        else:
            ret = json.load(open(f"core/languages/{self.bot.lang.default}.json"))["cogs"][cog]

        return ret["commands"][self.command.qualified_name]
