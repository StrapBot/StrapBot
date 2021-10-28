import asyncio
import os
import json
import typing
from discord.ext.commands import Bot


class Config:
    def __init__(self, bot: Bot):
        from strapbot import StrapBot  # I want colored syntax and suggestions

        self.bot: StrapBot = bot
        self.db = self.bot.db.Config
        self.base = {
            "lang": str,
        }
        self.users_base = {"beta": bool}
        self.guilds_base = {"logchannel": int, "youtube": None}

    def get_idtype(self, id: int) -> str:
        return (
            type(self.bot.get_user(id) or self.bot.get_guild(id)).__name__.lower()
            + "s"  # BUG: this might return "nonetypes", dont want to fix it
        )

    def get_base(self, type_: str) -> dict:
        ret = dict(self.base)  # create another instance
        ret.update(getattr(self, f"{type_}_base", {}))
        return ret

    async def create_base(self, id: int, guild_id: int = None) -> dict:
        _id = self.get_idtype(id)
        if _id == "users" and (guild_id is None or not isinstance(guild_id, int)):
            raise ValueError(
                f"When creating a base for a user, a `guild_id` must be given."
                if guild_id is None
                else f"Expected `int` on `guild_id`, got `{type(guild_id).__name__}`."
            )
        base = self.get_base(_id)
        data = {}
        for k, v in base.items():
            if v == None:
                # the value is special, it needs to be hidden,
                # most probably for internal stuff, or configs
                # managed by other commands
                if k == "youtube":
                    v = dict

            data[k] = v() if callable(v) else v

        await self.db.find_one_and_update(
            {"_id": _id}, {"$set": {str(id): data}}, upsert=True
        )

        return data

    async def find(self, id: int) -> dict:
        _id = self.get_idtype(id)
        return (await self.db.find_one({"_id": _id})).get(str(id), {})

    async def get(self, id: int, key: str, default=None):
        _id = self.get_idtype(id)
        data = (await self.db.find_one({"_id": _id}))[str(id)]

        return data.get(key, default)

    async def findall(self, type_) -> dict:
        if not type_ in ["guilds", "users"]:
            raise TypeError("type_ must be one between 'guilds' or 'users'.")
        return await self.db.find_one({"_id": type_})

    async def find_all(self) -> list:
        return await self.db.find().to_list(None)

    def is_kv_valid(self, key: str, value, lang="en"):
        lang = json.load(open(f"core/languages/{lang}.json"))["cogs"]["Config"][
            "commands"
        ]["config"]["errors"]
        langs = [f.replace(".json", "") for f in os.listdir("core/languages")]
        value_type = type(value).__name__
        if key == "lang":
            if value not in langs:
                ls = "'" + ("', '".join(langs)) + "'"
                raise ValueError(lang["lang"].format(ls))
        elif key == "beta":
            if not isinstance(value, bool):
                raise ValueError(f"beta must be a bool, not '{value_type}'")
        elif key == "logchannel":
            if not isinstance(value, int):
                raise ValueError(lang["logch"])
        return True

    async def set(self, id, lg="en", **kwargs) -> dict:
        _id = self.get_idtype(id)
        data = await self.find(id)

        for key, value in kwargs.items():
            self.is_kv_valid(key, value, lg)
            if not key in self.get_base(_id):
                raise KeyError(f"'{key}'")

            data[key] = value
            await asyncio.sleep(0)  # avoid blocking

        await self.db.find_one_and_update(
            {"_id": _id}, {"$set": {str(id): data}}, upsert=True
        )

        return data
