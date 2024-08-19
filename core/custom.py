from discord.ext.commands import *
from discord.ext.commands import Cog as _OriginalCog
from .context import StrapContext as Context
from strapbot import StrapBot as Bot
from random import choice as _choice
from discord.utils import maybe_coroutine as _maybe_coroutine
from discord import Object as _Object
from core.utils import get_logger as _get_logger

_logger = _get_logger(__name__)


class Cog(_OriginalCog):
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self._emoji = None

    @property
    def emoji(self):
        if self._emoji is None:
            emojis = [
                "\N{grinning face}",
                "\N{grinning face with smiling eyes}",
                "\U0001f643",
                "\N{face with stuck-out tongue}",
                "\N{face with stuck-out tongue and winking eye}",
                "\N{grinning face with one large and one small eye}",
                "\U0001fae1",
                "\U0001fae0",
                "\U0001fae5",
                "\N{clown face}",
                "\N{extraterrestrial alien}",
                "\N{smiling cat face with open mouth}",
                "\N{ok hand sign}",
                "\N{speaking head in silhouette}\N{variation selector-16}",
                "\N{sleuth or spy}\N{variation selector-16}\N{zero width joiner}\N{male sign}\N{variation selector-16}",
                "\N{man}\N{zero width joiner}\N{airplane}\N{variation selector-16}",
                "\N{monkey}",
                "\N{goat}",
                "\N{potato}",
                "\N{soft ice cream}",
                "\N{person with ball}\N{variation selector-16}\N{zero width joiner}\N{female sign}\N{variation selector-16}",
                "\N{personal computer}",
                "\N{keyboard}\N{variation selector-16}",
                "\N{electric light bulb}",
            ]
            return _choice(emojis)

        return self._emoji

    @emoji.setter
    def emoji(self, value):
        self._emoji = value

    @emoji.deleter
    def emoji(self):
        self._emoji = None

    # in our case, we need to force the cog and the commands
    # to only work in one guild, which is why we're gonna override
    # the _inject and _eject methods that should be used internally
    async def _inject(self, bot: Bot, override: bool, guild=None, guilds=None):
        self.bot = bot
        cls = self.__class__

        await _maybe_coroutine(self.cog_load)

        for i, command in enumerate(self.__cog_commands__):
            command.cog = self
            if command.parent is None:
                try:
                    bot.add_command(command)
                except Exception as e:
                    # undo our additions
                    for to_undo in self.__cog_commands__[:i]:
                        if to_undo.parent is None:
                            bot.remove_command(to_undo.name, guild_id=self.guild_id)
                    try:
                        await _maybe_coroutine(self.cog_unload)
                    finally:
                        raise e

        # check if we're overriding the default
        if cls.bot_check is not Cog.bot_check:
            bot.add_check(self.bot_check)

        if cls.bot_check_once is not Cog.bot_check_once:
            bot.add_check(self.bot_check_once, call_once=True)

        for name, method_name in self.__cog_listeners__:
            bot.add_listener(getattr(self, method_name), name)

        if not self.__cog_app_commands_group__:
            for command in self.__cog_app_commands__:
                bot.tree.add_command(
                    command, override=override, guild=_Object(id=self.guild_id)
                )

        return self

    async def _eject(self, bot: Bot, guild_ids=None) -> None:
        cls = self.__class__

        try:
            for command in self.__cog_commands__:
                if command.parent is None:
                    bot.remove_command(command.name, guild_id=self.guild_id)

            if not self.__cog_app_commands_group__:
                for command in self.__cog_app_commands__:
                    bot.tree.remove_command(
                        command.name, guild=_Object(id=self.guild_id)
                    )

            for name, method_name in self.__cog_listeners__:
                bot.remove_listener(getattr(self, method_name), name)

            if cls.bot_check is not Cog.bot_check:
                bot.remove_check(self.bot_check)

            if cls.bot_check_once is not Cog.bot_check_once:
                bot.remove_check(self.bot_check_once, call_once=True)

        finally:
            try:
                await _maybe_coroutine(self.cog_unload)
            except Exception:
                _logger.exception(
                    "Ignoring exception in cog unload for Cog %r (%r)",
                    cls,
                    self.qualified_name,
                )
