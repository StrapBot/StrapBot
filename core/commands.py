import inspect
import os
from discord.ext.commands import Command
from discord.utils import maybe_coroutine
from discord_slash.model import BaseCommandObject as SlashCommand, CogBaseCommandObject
from discord_slash.utils import manage_commands

# I added this line below so I can just replace
# discord.ext.commands -> core.commands
from discord.ext.commands import *


class CogSlashCommand(CogBaseCommandObject):
    async def can_run(self, ctx) -> bool:
        can_actually_run = await super().can_run(ctx)
        cog_check = True
        if self.cog:
            cog_check = await maybe_coroutine(self.cog.cog_check, ctx)

        return can_actually_run and cog_check


class StrapBotCommand(Command):
    def __init__(self, func, **kwargs):
        is_slash = isinstance(func, (SlashCommand, CogSlashCommand))
        self.slash = func if is_slash else None
        func = func.func if is_slash else func
        self.slash_args = kwargs.get("slash_args", {})
        super().__init__(func, **kwargs)

    def update(self, **kwargs):
        """Updates :class:`Command` instance with updated attribute.

        This works similarly to the :func:`.command` decorator in terms
        of parameters in that they are passed to the :class:`Command` or
        subclass constructors, sans the name and callback.
        """

        callback = self.slash or self.callback
        
        self.__init__(callback, **dict(self.__original_kwargs__, **kwargs))

    def _update_copy(self, kwargs):
        if kwargs:
            kw = kwargs.copy()
            kw.update(self.__original_kwargs__)
            callback = self.slash or self.callback
            copy = self.__class__(callback, **kw)
            return self._ensure_assignment_on_copy(copy)
        else:
            return self.copy()

    def copy(self):
        """Creates a copy of this command.

        Returns
        --------
        :class:`Command`
            A new instance of this command.
        """
        callback = self.slash or self.callback

        ret = self.__class__(callback, **self.__original_kwargs__)
        return self._ensure_assignment_on_copy(ret)


def command(name: str = None, cls: type = None, **attrs):
    if cls == None:
        cls = StrapBotCommand
    _slash_attrs = [
        "name",
        "description",
        "guild_ids",
        "options",
        "default_permission",
        "permissions",
        "connector",
    ]
    klass = CogSlashCommand
    if not attrs.get("cog", True):
        klass = SlashCommand
    slash_attrs = {"has_subcommands": False}
    for attr in _slash_attrs:
        attr_name = f"api_{attr}" if attr in ["options", "permissions"] else attr
        if attr in attrs:
            slash_attrs[attr_name] = attrs[attr]
        else:
            if attr == "guild_ids":
                slash_attrs[attr_name] = []
            elif attr == "connector":
                slash_attrs[attr_name] = {}
            else:
                slash_attrs[attr_name] = None

    # NEVER USE THIS ENVIRONMENT VARIABLE.
    # It's used by me for the private testing bot.
    if os.getenv("SB__ENVIRONMENT", "") == "dev":
        slash_attrs["guild_ids"].append(int(os.getenv("MAIN_GUILD_ID")))

    def decorator(func):

        decorator_permissions = getattr(func, "__permissions__", None)
        if decorator_permissions:
            slash_attrs["api_permissions"].update(decorator_permissions)

        desc = slash_attrs["description"] or inspect.getdoc(func)
        if not "api_options" in slash_attrs or not slash_attrs["api_options"]:
            slash_attrs["api_options"] = manage_commands.generate_options(
                func, desc, slash_attrs["connector"]
            )
        slash_attrs["func"] = func
        if isinstance(func, Command):
            raise TypeError("Callback is already a command.")

        if not attrs.get("hidden", False):
            func = klass(name or func.__name__, slash_attrs)

        ret = func
        if not attrs.get("slash_only", False):
            ret = cls(func, name=name, slash_args=slash_attrs, **attrs)
        
        return ret

    return decorator
