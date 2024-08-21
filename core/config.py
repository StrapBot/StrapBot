import os
import discord
from .utils import (
    DEFAULT_LANG_ENV,
    lang_exists,
    get_langs_properties,
    get_lang_config_names,
    get_flag_emoji,
    get_logger,
)
from discord.ext import commands
from discord import TextChannel, Thread, ChannelType, SelectOption
from discord.enums import ComponentType, TextStyle
from enum import Enum
from typing import Optional, Union, Type, List, Dict, Any
from functools import partial


def get_lang_props(lang: str, key: Any, folder=None):
    # _ = lambda: get_lang_config_names(os.getenv(DEFAULT_LANG_ENV, "en"))
    def _():
        if folder:
            return (
                get_lang_config_names(os.getenv(DEFAULT_LANG_ENV, "en"))
                .get(folder.key, {})
                .get("items", {})
            )

        return get_lang_config_names(os.getenv(DEFAULT_LANG_ENV, "en"))

    props = get_lang_config_names(lang)
    if folder:
        props = props.get(folder.key, {}).get("items", {})

    if not props:
        props = _()

    if key not in props:
        props = _()
        if key not in props:
            return {
                "name": key,
                "description": f"Information for configuration `{key}` not found.",
            }

    return props[key]  # type: ignore


def _make_base(d):
    ret = {}
    for k, t in d.items():
        if (
            t.select_menu_type
            and t.select_menu_type.max_values > 1
            and t.select_menu_type.min_values < t.select_menu_type.max_values
            and t.default is None
        ):
            ret[k] = []
        else:
            ret[k] = t.default

    return ret


class ConfigValueError(ValueError):
    pass


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
    inputs = {}
    select_menu_type: Optional[SelectMenuType] = None

    def __new__(cls, value: Any, bot: commands.Bot) -> Optional[Any]:
        if cls.validate(value, bot):
            return cls.transform(value)
        elif value != None:
            # the configuration has been set but the value isn't valid
            raise ConfigValueError(
                f"Value {value!r} is not valid for config {cls.key}."
            )

    @classmethod
    def can_be_set(cls, config, guild_config) -> bool:
        return True

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

    @classmethod
    def transform(cls, val: Any):
        return val


class FolderConfigType(ConfigType):
    pass


class FolderConfigData(dict):
    def __init__(self, base: Type[FolderConfigType], data: dict, parent=None):
        super().__init__(data)
        self.__base = base
        self.parent = parent

    def __getattr__(self, item):
        return getattr(self.__base, item)

    def __call__(self, value: Any, bot: commands.Bot):
        return self.__base(value, bot)

    def validate(self, val: dict, bot: commands.Bot):
        return all(a.validate(val.get(k, val.get(a.key)), bot) for k, a in self.items())

    @property
    def default(self):
        return _make_base(self)

    @property
    def emojis(self):
        return {k: a.emoji for k, a in self.items()}


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


class ModerationConfigType(GuildConfigType, FolderConfigType):
    key = "moderation"
    emoji = "\N{shield}"


class MutedRoleType(ModerationConfigType):
    key = "muted_role_id"
    emoji = "\N{speaker with cancellation stroke}"
    select_menu_type = SelectMenuType(
        MenuType.role,
        1,
        1,
    )

    @staticmethod
    def validate(val: Union[discord.Role, int], bot: commands.Bot) -> bool:
        if isinstance(val, int) or not isinstance(val, discord.Role):
            if not isinstance(val, int):
                return False

            guild = discord.utils.find(lambda g: g.get_role(val), bot.guilds)  # type: ignore
            if guild == None:
                return False

            val = guild.get_role(val)
            if val == None:
                return False

        return val.guild.me.top_role.position > val.position  #  type: ignore


class TimeoutType(ModerationConfigType):
    key = "timeout"
    default = False
    emoji = "\N{hourglass}"

    @staticmethod
    def validate(val: bool, bot: commands.Bot):
        return isinstance(val, bool)


class LogChannelType(ModerationConfigType):
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
    def validate(
        cls, val: Optional[Union[TextChannel, Thread, int]], bot: commands.Bot
    ):
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


class YouTubeNewsType(GuildConfigType, FolderConfigType):
    key = "yt_news"
    emoji = "\N{film frames}"


class YouTubeNewsChannelType(YouTubeNewsType):
    key = "channel_id"
    emoji = "\N{public address loudspeaker}"
    select_menu_type = SelectMenuType(
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
            avatar=(
                await value.guild.me.avatar.read() if value.guild.me.avatar else None
            ),
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


class YouTubeNewsMessageType(YouTubeNewsType):
    key = "message"
    emoji = "\N{memo}"
    default = "{video}"
    custom = True
    inputs = {"message": TextStyle.paragraph}


class MarkovChainType(GuildConfigType, FolderConfigType):
    key = "markov"
    emoji = "\N{writing hand}"


class MarkovChainEnabledType(MarkovChainType):
    key = "enabled"
    emoji = "\N{gear}"
    default = False

    @staticmethod
    def validate(val: bool, bot: commands.Bot):
        return isinstance(val, bool)

    @staticmethod
    async def setup(ctx: commands.Context, value: bool):
        if value:
            db = ctx.bot.get_db("MarkovChain", False)
            res = await db.find_one({"_id": ctx.guild.id})  # type: ignore
            if res:
                return

            cf = ctx.guild_config  # type: ignore
            await ctx.send(
                "markov_enabled",
                ephemeral=True,
                lang_to_use=get_lang_props(
                    ctx.language_to_use,  # type: ignore
                    "enabled",
                    folder=cf.types["markov"],
                ),
            )  # type: ignore
            c = cf["markov"].copy()  #  type: ignore
            c["channel_id"] = ctx.channel.id
            await cf.set(markov=c)  # type: ignore
            await MarkovChainChannelType.setup(ctx, ctx.channel.id)


class MarkovChainChannelType(MarkovChainType):
    key = "channel_id"
    emoji = "\N{page with curl}"
    select_menu_type = SelectMenuType(
        MenuType.channel,
        1,
        1,
        [ChannelType.text],
    )

    @staticmethod
    def channel_check(channel) -> bool:
        if not isinstance(channel, TextChannel):
            return False

        perms = channel.permissions_for(channel.guild.me)
        return perms.administrator or perms.send_messages

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

        return cls.channel_check(chn) and chn.guild.id not in bot.markov_learn_events  # type: ignore

    @classmethod
    async def get_valid_values(cls, ctx: commands.Context) -> list:
        return list(filter(cls.channel_check, getattr(ctx.guild, "channels", [])))

    @classmethod
    def can_be_set(cls, config, guild_config) -> bool:
        return guild_config.markov["enabled"]

    @staticmethod
    async def setup(ctx: commands.Context, value: int):
        bot = ctx.bot
        db = bot.get_db("MarkovChain", False)
        res = await db.find_one({"_id": ctx.guild.id})  # type: ignore
        if res and value == res["channel_id"]:
            return
        elif res:
            await db.delete_one({"_id": ctx.guild.id})  #  type: ignore

        await db.insert_one({"_id": ctx.guild.id, "channel_id": value})  # type: ignore

        setup_chn = get_lang_props(
            ctx.language_to_use,  # type: ignore
            "channel_id",
            folder=ctx.guild_config.types["markov"],  # type: ignore
        )

        # importing here to avoid circular imports
        from .views.misc import MarkovChannelSetupView

        await ctx.send(
            "channel_history_fetch",
            ephemeral=True,
            view=MarkovChannelSetupView(
                ctx,  # type: ignore
                db,
                lang=setup_chn,
            ),
            lang_to_use=setup_chn,
        )


class MarkovMessagesType(MarkovChainType):
    key = "messages"
    default = {"min": 5, "max": 10, "words": 20}
    custom = True
    inputs = {
        "min": TextStyle.short,
        "max": TextStyle.short,
        "words": TextStyle.short,
    }

    @staticmethod
    def _intify(n):
        if isinstance(n, int):
            return n

        try:
            return int(n)
        except ValueError:
            return 0

    @classmethod
    def validate(cls, val: dict, bot: commands.Bot):
        if all(not isinstance(a, int) and not a.isdigit() for a in val.values()):
            return False

        val = val.copy()
        for k, v in val.items():
            val[k] = cls._intify(v)

        return (
            all(a >= 0 for a in val.values())
            and val["min"] <= val["max"]
            and val["min"] > 1
            and val["max"] <= 100
            and 10 <= val["words"] <= 100
        )

    @classmethod
    def can_be_set(cls, config, guild_config) -> bool:
        return guild_config.markov["enabled"]

    @classmethod
    def transform(cls, val: Any):
        return {k: cls._intify(v) for k, v in val.items()}


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


class MarkovAddMyMessagesType(UserConfigType):
    key = "markov_add_my_messages"
    emoji = "\N{brain}"
    default = True

    @staticmethod
    def validate(val: bool, bot: commands.Bot):
        return isinstance(val, bool)

    @classmethod
    def can_be_set(cls, config, guild_config) -> bool:
        return guild_config.markov["enabled"]


try:
    from custom.configs import *  # type: ignore
except ImportError:
    get_logger().debug("Custom configurations not found.")
except Exception as e:
    get_logger().error("Could not load custom configurations.", exc_info=e)

ConfigTypes = Dict[str, Union[Type[ConfigType], FolderConfigData]]


class Config:
    def __init__(
        self,
        bot,
        types: Optional[ConfigTypes] = None,
        **data,
    ):
        from strapbot import StrapBot  # sorry but I like specifying types

        self.bot: StrapBot = bot
        self._data: dict = data
        self.types: ConfigTypes = types or self._create_types()
        self.emojis = {k: t.emoji for k, t in self.types.items()}
        self.base: Dict[str, Any] = self._create_base()
        self.id = data["_id"]
        self.db = self.bot.get_db("Configurations", cog=False)

    def __check(self, base, entry, types, force=False):
        modified = False
        for k, v in base.items():
            if k not in types and force:
                raise KeyError(k)

            if k not in entry or force:
                modified = True
                entry[k] = types[k](v, self.bot)

            if isinstance(v, dict) and not types[k].custom:
                ch = self.__check(base[k], entry[k], types[k], force)
                modified = ch or modified

        return modified

    @staticmethod
    def _create_types(
        tp: Optional[Union[Type[GuildConfigType], Type[UserConfigType]]] = None
    ) -> ConfigTypes:
        ret: ConfigTypes = {
            t.key: t
            for t in GlobalConfigType.__subclasses__()
            + (tp.__subclasses__() if tp else [])
        }

        for sc in FolderConfigType.__subclasses__():
            if not issubclass(sc, GlobalConfigType) and (tp and not issubclass(sc, tp)):
                continue

            ret[sc.key] = FolderConfigData(sc, {t.key: t for t in sc.__subclasses__()})

        return ret

    def _create_base(self) -> Dict[str, Any]:
        return _make_base(self.types)

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
        entry = self._data.copy()

        modified = self.__check(self.base, entry, self.types)

        if modified or update:
            if modified:
                await self.db.update_one({"_id": self.id}, {"$set": entry})  # type: ignore
            self._data: dict = await self.db.find_one({"_id": self.id})  # type: ignore

        self._data.pop("type", None)
        # self.__data["id"] = self.__data.pop("_id", self.id)
        return self._data

    @classmethod
    async def create_config(
        cls, bot, target: Union[discord.User, discord.Guild]
    ) -> Union["Config", "GuildConfig", "UserConfig"]:
        """Create a config class"""
        if not target:
            raise Exception
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
        await ret.fetch(True)

        return ret

    async def set(self, **props):
        new = self._data.copy()
        new["type"] = type(self.target).__name__.lower()
        modified = self.__check(props, new, self.types, True)

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
