import os
import json
import random
import shutil
import logging
import asyncio
import unicodedata
from rich.logging import RichHandler
from typing import List, Optional, Union
from pyfiglet import Figlet
from discord.ext import commands
from discord.app_commands import (
    Translator,
    locale_str,
    TranslationContextTypes,
    TranslationContextLocation as TCL,
    ContextMenu,
    Group as AppGroup,
    Parameter,
    Choice,
)
from discord.ext.commands import (
    Command,
    Group,
    HybridCommand,
    HybridGroup,
    HelpCommand,
    DefaultHelpCommand,
    MinimalHelpCommand,
)
from discord.ext.commands.hybrid import HybridAppCommand
from discord.enums import Locale
from functools import partial

AnyCommand = Union[
    Command,
    HelpCommand,
    DefaultHelpCommand,
    MinimalHelpCommand,
    HybridCommand,
    HybridAppCommand,
]

# app commands' Group isn't here because it misses cog
AnyGroup = Union[HybridGroup, Group]

DEFAULT_LANG_ENV = "DEFAULT_LANGUAGE"
LANGS_PATH = os.path.abspath("./langs")


class LoggingHandler(RichHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_time = self._log_render.show_time
        self.show_level = self._log_render.show_level
        self.show_path = self._log_render.show_path
        self.iconsole = None

    def emit(self, record: logging.LogRecord) -> None:
        if self.iconsole:
            print(end="\r")
        self._log_render.show_time = getattr(record, "show_time", self.show_time)
        self._log_render.show_level = getattr(record, "show_level", self.show_level)
        self._log_render.show_path = getattr(record, "show_path", self.show_path)

        super().emit(record)

    def render_message(self, record: logging.LogRecord, message: str):
        return super().render_message(record, message.strip("\n"))


def get_flag_emoji(code):
    ret = ""
    # this isn't the best way ever of course, but at least it works
    for l in list(code):
        ret += unicodedata.lookup(f"regional indicator symbol letter {l}")

    return ret


handler = LoggingHandler(markup=True)


def configure_logging():
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%d/%m/%Y %X]",
        handlers=[handler],
    )


def get_logger(name: str = ""):
    if not name:
        name = "strapbot"
    else:
        name = f"strapbot.{name}"

    return logging.getLogger(name)


def raise_if_no_env(envvar: str, exc: Exception):
    """
    A function that raises an exception
    if an environment variable is missing.
    """
    var = os.getenv(envvar, None)
    if var == None:
        raise exc

    return var


def get_startup_text(version: str, font: str = ""):
    """
    A function that generates the text
    that is used before the startup.
    """
    text1 = ""
    spaces = ""
    if shutil.get_terminal_size((0, 0)).columns >= 129:
        font = font or random.choice(
            ["jazmine", "letters", "lean", "nipples", "poison", "shadow", "standard"]
        )
        fl = Figlet(font=font, justify="left", width=100)

        textlines = fl.renderText("StrapBot!").splitlines()
        text1l = []
        length = 0

        for line in textlines:
            text1l.append(f"[bold]{line}[/]")
            _len = len(line)
            if _len > length:
                length = _len

        inittext = "Welcome to..."
        _spcs = " " * round((length - len(inittext)) / 2)
        text1 = _spcs + inittext + "\n" + ("\n".join(text1l))
        spaces = " " * round((length - len("StrapBot " + version)) / 2)
        text1 += "\n"

    text2 = spaces + f"[bold]StrapBot[/] {version}"
    return f"\n{text1}{text2}\n\n"


def get_langs() -> List[str]:
    ret = []
    f = lambda d: os.path.isdir(os.path.join(LANGS_PATH, d))
    for d in filter(f, os.listdir(LANGS_PATH)):
        datapath = os.path.join(LANGS_PATH, d, "__data__.json")
        if os.path.exists(datapath):
            data = json.load(open(datapath))
            ret.append(data["code"])

    return ret


def lang_exists(lang: str):
    return lang in get_langs()


def try_lang(lang: str) -> str:
    if not lang_exists(lang):
        lang = os.getenv(DEFAULT_LANG_ENV, "en")

    return lang


def get_lang_command_file_path(lang: str, command: Union[AnyCommand, AnyGroup]) -> str:
    """Get the file path of a command's translations, without checking anything."""
    cog = getattr(command, "cog", getattr(command, "binding", None))
    cog_name = type(cog).__name__ if cog != None else None
    if isinstance(command, HelpCommand):
        command_name = "help"
    else:
        command_name = command.name

    # "commands" is for commands without a cog,
    # which is unlikely going to happen anyway
    fp = os.path.join(
        LANGS_PATH,
        lang,
        os.path.join("cogs", cog_name) if cog_name != None else "commands",
    )
    parent: Optional[AnyGroup] = getattr(command, "parent", None)
    parents: List[str] = []
    while parent != None:
        parents.append(parent.name)
        parent = parent.parent  # type: ignore

    fp = os.path.join(os.path.join(fp, *reversed(parents)), command_name)

    # I wanted to make something long
    if (
        os.path.isdir(fp) and os.path.exists(os.path.join(fp, "__data__.json"))
    ) or isinstance(command, Group):
        return os.path.join(fp, "__data__.json")
    else:
        return f"{fp}.json"


def get_command_lang_file(
    lang: str, command: Union[AnyCommand, AnyGroup]
) -> Optional[str]:
    """Get the file path of a command's translations. Returns None if a check fails."""
    lang = try_lang(lang)

    ret = get_lang_command_file_path(lang, command)
    if os.path.exists(ret):
        return ret
    else:
        lang = os.getenv(DEFAULT_LANG_ENV, "en")
        ret = get_lang_command_file_path(lang, command)
        if os.path.exists(ret):
            return ret


def get_lang_properties_file(lang: str, file: str) -> Optional[dict]:
    lang = try_lang(lang)

    path = lambda l: os.path.join(LANGS_PATH, l, file)
    if not os.path.exists(path(lang)):
        lang = os.getenv(DEFAULT_LANG_ENV, "en")
        if not os.path.exists(path(lang)):
            return

    return json.load(open(path(lang)))


def get_lang_properties(lang: str) -> Optional[dict]:
    return get_lang_properties_file(lang, "__data__.json")


def get_langs_properties() -> List[dict]:
    return [get_lang_properties(lang) for lang in get_langs()]  # type: ignore


def get_lang_config_names(lang: str) -> Optional[dict]:
    return get_lang_properties_file(lang, "configs.json")


def get_lang(
    lang: str,
    *,
    cog: Optional[commands.Cog] = None,
    command: Optional[Union[AnyCommand, Choice]] = None,
) -> Optional[dict]:
    lang = try_lang(lang)

    fp = os.path.join(LANGS_PATH, lang)
    if isinstance(command, Choice):
        fp = os.path.join(fp, "choices.json")
    else:
        command_cog = getattr(command, "cog", getattr(command, "binding", None))
        if (cog != None and command != None) and (type(command_cog) != type(cog)):
            raise ValueError("You can't give a command from a different cog.")

        if cog == None and command == None:
            raise ValueError("Either cog or command must be given.")

        cog = cog or command_cog  # type: ignore # At least one of the twos must not be None

        if cog != None and command == None:
            fp = os.path.join(
                fp,
                "cogs",
                type(cog).__name__,
                f"__data__.json",
            )
        elif command != None:
            fp = get_command_lang_file(lang, command)
            if fp == None:
                return

    if not os.path.exists(fp):
        return

    return json.load(open(fp))


class MyTranslator(Translator):
    async def translate(
        self, string: locale_str, locale: Locale, context: TranslationContextTypes
    ) -> Optional[str]:
        loop = asyncio.get_event_loop()
        # country-specific locales haven't been implemented yet
        lang = locale.value.split("-")[0]

        # context menus and groups are to be implemented
        if isinstance(context.data, (ContextMenu, AppGroup)):
            return

        command = context.data
        if isinstance(context.data, Parameter):
            command = context.data.command
        props = await loop.run_in_executor(
            None, partial(get_lang, lang, command=command)  #  type: ignore
        )
        props_check = lambda: props == None or (
            isinstance(command, Choice) and command.name not in props
        )
        if props == None or props_check():
            default = os.getenv(DEFAULT_LANG_ENV, "en")
            props = get_lang(default, command=command)  # type: ignore
            if props == None or props_check():
                return

        if context.location == TCL.choice_name:
            return props[command.name]
        elif context.location == TCL.command_description:
            if props == None:
                return
            return props["short_doc"]
        elif context.location in [TCL.parameter_name, TCL.parameter_description]:
            if "params" not in props:
                return

            params = props["params"]
            param = params[context.data.name]
            attr = (
                "description"
                if context.location == TCL.parameter_description
                else "name"
            )
            return param[attr]
