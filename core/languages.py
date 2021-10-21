import box
import os
import discord
import json

default_language = os.getenv("DEFAULT_LANGUAGE", "en")


class Language(box.Box):
    def __repr__(self):
        return f"<Language current={repr(self.current)}>"


class Languages:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db.db["Config"]
        self.default = os.getenv("DEFAULT_LANGUAGE", "en")
        self.get_users = self.get_members

    async def get_guilds(self):
        return await self.db.find_one({"_id": "guilds"})

    async def get_members(self):
        return await self.db.find_one({"_id": "users"})

    async def get_guild(self, guild: int = None):
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
        else:
            return ret

    async def set_guild(
        self, guild: int = None, member: int = None, *, lang: str = default_language
    ):
        if lang != "en" and lang != "it" and not "testù" in lang:
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
        data = (await self.db.find_one({"_id": "users"})).get(str(guild.id)) or {}
        data["language"] = lang

        return await self.db.find_one_and_update(
            {"_id": "guilds"},
            {"$set": {str(guild.id): data}},
            upsert=True,
        )

    async def get_user(self, member: int = None):
        if member == None:
            raise RuntimeError("You must give a user ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID")

        return await self.db.find_one({"_id": "users"})

    async def set_user(self, member: int = None, *, lang: str = default_language):
        if lang != "en" and lang != "it" and not "testù" in lang:
            raise TypeError("Unknown language.")

        if member == None:
            raise RuntimeError("You must give a user ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID")

        data = (await self.db.find_one({"_id": "users"})).get(str(member.id)) or {}
        data["language"] = lang

        return await self.db.find_one_and_update(
            {"_id": "users"},
            {"$set": {str(member.id): data}},
            upsert=True,
        )

    async def unset_user(self, member: int = None):
        if member == None:
            raise RuntimeError("You must give a user ID.")

        member = discord.utils.get(self.bot.get_all_members(), id=member)
        if member == None:
            raise TypeError("Invalid user ID")

        return await self.db.find_one_and_update(
            {"_id": "users"}, {"$unset": {str(member.id): {}}}, upsert=True
        )

    async def fetch_user_lang(self, ctx, user: int = None):
        if user == None:
            user = ctx.author.id
        member = discord.utils.get(self.bot.get_all_members(), id=user)
        if member == None:
            raise TypeError("Invalid user ID")

        members = await self.db.find_one({"_id": "users"})
        guilds = await self.db.find_one({"_id": "guilds"})
        try:
            current = members[str(user)]
        except KeyError:
            try:
                current = guilds[str(ctx.guild.id)]
            except KeyError:
                current = self.default
            else:
                current = current["language"]
        else:
            current = current["language"]
        ret = json.load(open(f"core/languages/{current}.json"))
        ret = ret["cogs"][ctx.command.cog.__class__.__name__]["commands"][
            ctx.command.qualified_name
        ]

        ret["current"] = current
        ret = Language(ret)
        return ret

    async def fetch_guild_lang(self, ctx, *, guild: int = None):
        if guild == None and ctx != None:
            guild = ctx.guild.id
        guild = self.bot.get_guild(guild)
        if guild == None:
            raise TypeError("Invalid guild ID")

        guilds = await self.db.find_one({"_id": "guilds"})
        try:
            current = guilds[str(guild.id)]
        except KeyError:
            current = self.default
        else:
            current = current["language"]
        ret = json.load(open(f"core/languages/{current}.json"))
        ret = ret["cogs"][ctx.command.cog.__class__.__name__]["commands"][
            ctx.command.qualified_name
        ]

        ret["current"] = current
        ret = Language(ret)
        return ret
