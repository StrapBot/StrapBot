import os
import discord
from .utils import lang_exists, get_langs_properties, get_flag_emoji
from discord.ext import commands
from discord import TextChannel, Thread, ChannelType, SelectOption
from discord.enums import ComponentType, TextStyle
from enum import Enum
from typing import Optional, Union, Type, List, Dict, Any
from functools import partial


class MenuType(Enum):
    string = ComponentType.select
    user = ComponentType.user_select
    role = ComponentType.role_select
    mentionable = ComponentType.mentionable_select
    channel = ComponentType.channel_select


class SelectMenuType:
    def __init__(
        self,
        type: MenuType,
        min: int,
        max: Optional[int] = None,
        channel_types: Optional[List[ChannelType]] = None,
    ):
        if type == MenuType.channel:
            self.channel_types = channel_types or []

        self.type = type
        if min < 0 or min > 25:
            raise RuntimeError(
                "min must be greater than or equal to 0 and less than or equal to 25"
            )

        if max != None:
            if max < min:
                raise RuntimeError("max must be greater than min")

            if max > 25 or max < 1:
                raise RuntimeError(
                    "max must be greater than or equal to 1 and less than or equal to 25"
                )
        else:
            max = min
            min = 1

        self.min_values = min
        self.max_values = max

    def __repr__(self):
        return f"<{type(self).__name__} type={self.type.name!r} min_values={self.min_values!r} max_values={self.max_values!r}>"


# NOTE: "custom" is always overridden, "select_menu_type"
#       will only be used if "custom" is False.
class ConfigType:
    key = ""
    emoji = ""
    default: Any = None
    custom: bool = False
    text_style: Optional[TextStyle] = None
    select_menu_type: Optional[SelectMenuType] = None

    def __new__(cls, value: Any, bot: commands.Bot) -> Optional[Any]:
        if cls.validate(value, bot):
            return value
        else:
            raise ValueError(f"Value {value!r} is not valid for config {cls.key}.")

    @staticmethod
    def validate(val: Any, bot: commands.Bot):
        return True

    @staticmethod
    async def get_valid_values(ctx: commands.Context) -> list:
        return []

    @classmethod
    async def get_select_menu_values(cls, ctx: commands.Context) -> List[SelectOption]:
        return []

    @classmethod
    async def setup(cls, ctx: commands.Context, value):
        pass


# NOTE: to create a new configuration, you have to
#       subclass one of these three classes below,
#       depending on the configuration you want to
#       create.

# Global configurations (for both users and guilds)
class GlobalConfigType(ConfigType):
    pass


class LanguageType(GlobalConfigType):
    key = "lang"
    emoji = "\N{world map}"
    default = os.getenv("DEFAULT_LANGUAGE", "en")
    select_menu_type = SelectMenuType(MenuType.string, 1)

    @staticmethod
    def validate(val, bot):
        if isinstance(val, dict):
            val = val["code"]

        return lang_exists(val)

    @staticmethod
    async def get_valid_values(ctx: commands.Context) -> list:
        return get_langs_properties()

    @classmethod
    async def get_select_menu_values(cls, ctx: commands.Context) -> List[SelectOption]:
        vals = get_langs_properties()
        ret = []
        for val in vals:
            e = await ctx.bot.loop.run_in_executor(
                None, partial(get_flag_emoji, val["flag_code"])
            )
            opt = SelectOption(label=val["name"], value=val["code"], emoji=e)
            ret.append(opt)

        return ret


# Guild only configurations
class GuildConfigType(ConfigType):
    pass


class GuildLangOverrideType(GuildConfigType):
    default = False
    key = "override_guild_lang"

    @staticmethod
    def validate(val: bool, bot: commands.Bot):
        return isinstance(val, bool)


class LogChannelType(GuildConfigType):
    key = "log_channel_id"
    emoji = "\N{page facing up}"
    select_menu_type = SelectMenuType(
        MenuType.channel,
        1,
        1,
        [ChannelType.text, ChannelType.public_thread, ChannelType.private_thread],
    )

    @staticmethod
    def chn_check(chn) -> bool:
        if not isinstance(chn, (TextChannel, Thread)):
            return False

        perms = chn.permissions_for(chn.guild.me)
        sm = perms.send_messages
        if isinstance(chn, Thread):
            sm = perms.send_messages and perms.send_messages_in_threads

        el = perms.embed_links
        af = perms.attach_files
        admin = perms.administrator
        return admin or (sm and el and af)

    @classmethod
    def validate(cls, val: int, bot: commands.Bot):
        if val == None:
            return True  # value might be not set yet

        if not isinstance(val, (TextChannel, Thread)):
            if not isinstance(val, int):
                return False

            chn = bot.get_channel(val)
            if chn == None or not isinstance(chn, (TextChannel, Thread)):
                return False
        else:
            chn = val

        return cls.chn_check(chn)

    @classmethod
    async def get_valid_values(cls, ctx: commands.Context) -> list:
        return list(filter(cls.chn_check, getattr(ctx.guild, "channels", [])))


class YouTubeNewsChannelType(GuildConfigType):
    key = "yt_news_channel_id"
    emoji = "\N{public address loudspeaker}"
    select_menu_type = select_menu_type = SelectMenuType(
        MenuType.channel,
        1,
        1,
        [ChannelType.text, ChannelType.news],
    )

    @staticmethod
    def channel_check(channel) -> bool:
        if not isinstance(channel, TextChannel):
            return False

        perms = channel.permissions_for(channel.guild.me)
        return perms.administrator or perms.manage_webhooks

    @classmethod
    def validate(cls, val: int, bot: commands.Bot):
        if val == None:
            return True  # value might be not set yet

        if not isinstance(val, TextChannel):
            if not isinstance(val, int):
                return False

            chn = bot.get_channel(val)
            if chn == None or not isinstance(chn, TextChannel):
                return False
        else:
            chn = val

        return cls.channel_check(chn)

    @classmethod
    async def get_valid_values(cls, ctx: commands.Context) -> list:
        return list(filter(cls.channel_check, getattr(ctx.guild, "channels", [])))

    @staticmethod
    async def setup(ctx: commands.Context, value: discord.TextChannel):
        bot: commands.Bot = ctx.bot
        db = bot.get_db("YouTubeNewsGuilds", False)  # type: ignore
        if isinstance(value, int):
            value = ctx.guild.get_channel(value)  # type: ignore

        webhook = await value.create_webhook(
            name=value.guild.me.name,
            avatar=await value.guild.me.avatar.read()
            if value.guild.me.avatar
            else None,
        )

        cfg = await db.find_one({"_id": value.guild.id})
        if cfg != None:
            old_channel: Optional[TextChannel] = bot.get_channel(
                cfg["channel_id"]
            )  #  type: ignore
            if old_channel != None:
                old_wh = discord.utils.get(
                    await old_channel.webhooks(), url=cfg["webhook_url"]
                )
                if old_wh != None:
                    await old_wh.delete()

        await db.update_one(
            {"_id": value.guild.id},
            {"$set": {"channel_id": value.id, "webhook_url": webhook.url}},
            upsert=True,
        )


class YouTubeNewsMessageType(GuildConfigType):
    key = "yt_news_message"
    emoji = "\N{memo}"
    default = "{link}"
    custom = True
    text_style = TextStyle.paragraph


# User only configurations
class UserConfigType(ConfigType):
    pass


class PingOnReplyType(UserConfigType):
    key = "ping_on_reply"
    emoji = "\N{large red circle}"
    default = True

    @staticmethod
    def validate(val: bool, bot: commands.Bot):
        return isinstance(val, bool)


class Config:
    def __init__(
        self,
        bot,
        types: Optional[Dict[str, Type[ConfigType]]] = None,
        **data,
    ):
        from strapbot import StrapBot  # sorry but I like specifying types

        self.bot: StrapBot = bot
        self._data: dict = data
        self.types: Dict[str, Type[ConfigType]] = types or self._create_types()
        self.emojis = {k: t.emoji for k, t in self.types.items()}
        self.base: Dict[str, Any] = self._create_base()
        self.id = data["_id"]
        self.db = self.bot.get_db("Configurations", cog=False)

    @staticmethod
    def _create_types(
        tp: Optional[Union[Type[GuildConfigType], Type[UserConfigType]]] = None
    ) -> Dict[str, Type[ConfigType]]:
        return {
            t.key: t
            for t in GlobalConfigType.__subclasses__()
            + (tp.__subclasses__() if tp else [])
        }

    def _create_base(self) -> Dict[str, Any]:
        return {k: t.default for k, t in self.types.items()}

    @property
    def target(self) -> Union[discord.Guild, discord.User, None]:
        return self.bot.get_guild(self.id) or self.bot.get_user(self.id)

    @property
    def data(self):
        ret = self._data.copy()
        ret.pop("id", ret.pop("_id", None))
        typekeys = self.types.keys()
        for k in ret.copy().keys():
            if k not in typekeys:
                ret.pop(k, None)

        return ret

    def __getitem__(self, item):
        return self._data[item]

    def __getattr__(self, item):
        return self[item]

    def __repr__(self):
        attrs = []
        for k, v in self._data.items():
            attrs.append(f"{k}={v!r}")

        args = " ".join(attrs)
        return f"<{type(self).__name__} {args}>"

    async def fetch(self, update=False):
        """Update the entries to add new configurations."""
        modified = False
        entry = self._data.copy()
        for k, v in self.base.items():
            if k not in entry:
                modified = True
                entry[k] = self.types[k](v, self.bot)

        if modified or not update:
            if modified:
                await self.db.update_one({"_id": self.id}, {"$set": entry})  # type: ignore
            self._data: dict = await self.db.find_one({"_id": self.id})  # type: ignore

        self._data.pop("type", None)
        # self.__data["id"] = self.__data.pop("_id", self.id)
        return self._data

    @classmethod
    async def create_config(cls, bot, target: Union[discord.User, discord.Guild, None]):
        """Create a config class"""
        if not target:
            return
        db = bot.get_db("Configurations", cog=False)
        entry = await db.find_one({"_id": target.id})
        if not entry:
            entry = {}
            entry["_id"] = target.id
            entry["type"] = type(target).__name__.lower()
            await db.insert_one(entry)

        if entry["type"] == "user":
            cls = UserConfig
        elif entry["type"] == "guild":
            cls = GuildConfig

        ret = cls(bot, **entry)
        await ret.fetch()

        return ret

    async def set(self, **props):
        new = self._data.copy()
        new["type"] = type(self.target).__name__.lower()
        modified = False
        for key, value in props.items():
            if key not in self.types:
                raise KeyError(key)

            new[key] = self.types[key](value, self.bot)
            modified = True

        ret = new.copy()
        if modified:
            await self.db.update_one({"_id": self.id}, {"$set": new})  # type: ignore
            ret = await self.fetch(True)

        return ret


class UserConfig(Config):
    def __init__(self, bot, **data):
        super().__init__(bot, self._create_types(UserConfigType), **data)


class GuildConfig(Config):
    def __init__(self, bot, **data):
        super().__init__(bot, self._create_types(GuildConfigType), **data)


AnyConfig = Union[UserConfig, GuildConfig, Config]
