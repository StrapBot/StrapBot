import os
import discord

default_language = os.getenv("DEFAULT_LANGUAGE", "en")


class Languages:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db.db["LangConfig"]
        self.default = os.getenv("DEFAULT_LANGUAGE", "en")
        self.get_users = self.get_members

    async def get_guilds(self):
        return await self.db.find_one({"_id": "guilds"})

    async def get_members(self):
        return await self.db.find_one({"_id": "members"})

    async def get_guild(self, guild: int=None):
        if guild == None:
            raise RuntimeError("You must give a guild ID.")

        guild = self.bot.get_guild(guild)
        if guild == None:
            raise TypeError("Invalid guild ID.")

        ret = await self.db.find_one({"_id": "guilds"})
        try:
            ret = ret[str(guild.id)]
        except KeyError:
            return
        else: return ret

    async def set_guild(self, guild: int=None, member: int=None, *, lang: str=default_language):
        if lang != "en" and lang != "it" and lang != "../../testù":
            if lang == None:
                raise RuntimeError("You must specify a language.")
            raise TypeError("Unknown language.")
        if member == None:
            raise RuntimeError("You must give a user ID.")
        if guild == None:
            raise RuntimeError("You must give a guild ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID.")

        guild = self.bot.get_guild(guild)
        if guild == None:
            raise TypeError("Invalid guild ID.")
        
        await self.unset_user(member.id)

        return await self.db.find_one_and_update({"_id": "guilds"}, {"$set": {str(guild.id): {"language": lang}}}, upsert=True)

    async def get_user(self, member: int=None):
        if member == None:
            raise RuntimeError("You must give a user ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID")

        return await self.db.find_one({"_id": "members"})

    async def set_user(self, member: int=None, *, lang: str=default_language):
        if lang != "en" and lang != "it" and lang != "../../testù":
            raise TypeError("Unknown language.")

        if member == None:
            raise RuntimeError("You must give a user ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID")

        return await self.db.find_one_and_update({"_id": "members"}, {"$set": {str(member.id): {"language": lang}}}, upsert=True)

    async def unset_user(self, member: int=None):
        if member == None:
            raise RuntimeError("You must give a user ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID")

        return await self.db.find_one_and_update({"_id": "members"}, {"$unset": {str(member.id): {}}}, upsert=True)

        






    async def fetch_user_lang(self, ctx):
        return await ctx.get_lang()
