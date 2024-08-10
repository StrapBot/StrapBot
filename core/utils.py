import os
import re
import sys
import json
import pickle
import random
import shutil
import logging
import asyncio
import unicodedata
from rich.logging import RichHandler
from typing import Dict, List, Optional, Union, Any
from pyfiglet import Figlet
from discord.ext import commands
from datetime import datetime, timedelta
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
from collections import defaultdict, Counter
from motor.core import AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from gridfs import NoFile


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

time_regex = re.compile(r"(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400, "w": 604800}

DEFAULT_LANG_ENV = "DEFAULT_LANGUAGE"
LANGS_PATH = os.path.abspath("./langs")
IS_TERMINAL = sys.stdout.isatty() and sys.stderr.isatty()
PKL_NAME = "chn_{guild_id}.pkl"

# Debugging


def is_debugging() -> bool:
    return "debugpy" in sys.modules and sys.modules["debugpy"].is_client_connected()


if is_debugging():
    import types
    import concurrent.futures
    from pydevd import PyDB
    from _pydevd_bundle.pydevd_vars import _EvalAwaitInNewEventLoop as Original

    def get_debug_eval_in_loop_class(bot: commands.Bot) -> type:
        class _EvalAwaitInNewEventLoop(Original):
            def _on_run(self):
                try:
                    future = concurrent.futures.Future()

                    def callback():
                        try:
                            task_future = bot.loop.create_task(self._async_func())
                            asyncio.futures._chain_future(task_future, future)  # type: ignore
                        except BaseException as exc:
                            future.set_exception(exc)

                    bot.loop.call_soon_threadsafe(callback)
                    self.evaluated_value = future.result()
                except concurrent.futures.CancelledError:
                    pass
                except BaseException:
                    self.exc = sys.exc_info()

        return _EvalAwaitInNewEventLoop

    def get_debug_evaluate_expression(bot):
        def evaluate_expression(
            py_db: PyDB, frame: types.FrameType, expression: str, is_exec: bool
        ):
            frame.f_locals["bot"] = bot
            return bot._original_eval_exp(py_db, frame, expression, is_exec)

        return evaluate_expression


# Logging


class LoggingHandler(RichHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_time = self._log_render.show_time
        self.show_level = self._log_render.show_level
        self.show_path = self._log_render.show_path
        self.iconsole = None

    def render_message(self, record: logging.LogRecord, message: str):
        return super().render_message(record, message.strip("\n"))

    def emit(self, record: logging.LogRecord) -> None:
        if self.iconsole:
            print(end="\r")
        self._log_render.show_time = getattr(record, "show_time", self.show_time)
        self._log_render.show_level = getattr(record, "show_level", self.show_level)
        self._log_render.show_path = getattr(record, "show_path", self.show_path)

        super().emit(record)


HANDLER = LoggingHandler(markup=True, show_path=IS_TERMINAL)


def configure_logging():
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%d/%m/%Y %X]",
        handlers=[HANDLER],
    )


def get_logger(name: str = ""):
    if not name:
        name = "strapbot"
    else:
        name = f"strapbot.{name}"

    return logging.getLogger(name)


# Markov

ChainDict = Dict[str, Dict[str, int]]


class MarkovChain(defaultdict):
    """A message generator that uses a Markov chain."""

    def __init__(self, data: Optional[ChainDict] = None):
        super().__init__(Counter)
        if data:
            for key, value in data.items():
                self[key] = Counter(value)

    def __reduce__(self):
        return (self.__class__, (self.to_dict(),))

    def __getitem__(self, key: str) -> Counter[str]:
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: Counter[str]):
        super().__setitem__(key, value)

    def __repr__(self):
        return f"<{self.__class__.__name__} words={self.words}>"

    @property
    def words(self) -> int:
        """Return the amount of unique words in the Markov chain."""
        return len(self.keys())

    @staticmethod
    def _process_message(msg: str, d: ChainDict):
        words = [w for w in msg.split(" ") if w.strip(" ")]
        for i in range(len(words) - 1):
            current_word = words[i]
            next_word = words[i + 1]
            d[current_word][next_word] += 1

    @classmethod
    def from_messages(cls, *messages: str) -> "MarkovChain":
        """Create a Markov chain from a list of messages."""
        self = cls()
        for message in messages:
            self._process_message(message, self)

        return self

    @staticmethod
    def __to_dict(data: Dict[str, Counter[str]]) -> ChainDict:
        return {key: dict(value) for key, value in data.items()}

    def to_dict(self) -> ChainDict:
        """Convert the Markov chain to a dictionary for storing."""
        return self.__to_dict(self)

    def add_message(self, message: str) -> Dict[str, Counter[str]]:
        """
        Add a message to the Markov chain.
        Returns a dictionary containing the added words.
        """
        new = defaultdict(Counter)
        self._process_message(message, new)
        self.update(new)

        return self.__to_dict(new)

    def generate(self, length: int = 10) -> str:
        """Generate a message of a given length."""
        current_word = random.choice(list(self.keys()))
        message = [current_word]

        for _ in range(length - 1):
            next_words = self[current_word]
            if not next_words:
                break
            next_word = random.choices(
                list(next_words.keys()), weights=next_words.values()
            )[0]
            message.append(next_word)
            current_word = next_word

        return " ".join(message)


async def load_chain_from_db(
    db: AgnosticDatabase, guild_id: int
) -> Optional[MarkovChain]:
    fs = AsyncIOMotorGridFSBucket(db)

    try:
        data = await fs.open_download_stream_by_name(PKL_NAME.format(guild_id=guild_id))
    except NoFile:
        print("aaa")
        return

    try:
        return pickle.loads(await data.read())
    finally:
        data.close()


async def save_chain_to_db(
    db: AgnosticDatabase, guild_id: int, chain: MarkovChain
) -> None:
    fs = AsyncIOMotorGridFSBucket(db)
    name = PKL_NAME.format(guild_id=guild_id)

    # clean up all the older revisions before uploading
    async for file in fs.find({"filename": name}):
        await fs.delete(file._id)

    data = pickle.dumps(chain)
    print("saved", chain)
    await fs.upload_from_stream(name, data)


# Languages


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


def get_lang_properties_file(lang: str, file: str) -> dict:
    lang = try_lang(lang)

    path = lambda l: os.path.join(LANGS_PATH, l, file)
    if not os.path.exists(path(lang)):
        lang = os.getenv(DEFAULT_LANG_ENV, "en")
        if not os.path.exists(path(lang)):
            return {}

    return json.load(open(path(lang)))


def get_lang_properties(lang: str) -> dict:
    return get_lang_properties_file(lang, "__data__.json")


def get_langs_properties() -> List[dict]:
    return [get_lang_properties(lang) for lang in get_langs()]  # type: ignore


def get_lang_config_names(lang: str) -> dict:
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
            None, partial(get_lang, lang, command=command)  #  type: ignore
        )
        props_check = lambda: props == None or (
            isinstance(command, Choice) and command.name not in props
        )
        if props == None or props_check():
            default = os.getenv(DEFAULT_LANG_ENV, "en")
            props = await loop.run_in_executor(None, partial(get_lang, default, command=command))  # type: ignore
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


# Other


class TimeConverter(commands.Converter):
    def __init__(self, return_arg=False):
        self.return_arg = return_arg

    async def convert(self, ctx: commands.Context, argument: str):
        matches = time_regex.findall(argument.lower())
        time = 0
        if not matches and self.return_arg:
            return argument

        for v, k in matches:
            try:
                time += time_dict[k] * float(v)
            except KeyError:
                raise commands.BadArgument(
                    f"{k} is an invalid time-key! h/m/s/d/w are valid!"
                )
            except ValueError:
                raise commands.BadArgument(f"{v} is not a number!")
        return timedelta(seconds=time)


class StringOrTimeConverter(TimeConverter):
    def __init__(self):
        super().__init__(return_arg=True)


def paginate_list(lst: list, items: int):
    return [lst[i : i + items] for i in range(0, len(lst), items)]


def get_guild_youtube_channels(
    channels: List[Dict[str, Union[str, List[str]]]], guild_data: dict
):
    """
    channels must be the full list of channels in the YouTubeNews DB
    guild_data must be the guild entry in the YouTubeNewsGuilds DB
    """
    ret = guild_data.copy()
    ret["channels"] = []
    for item in channels:
        if guild_data["_id"] in item["guilds"]:
            ret["channels"].append(item["data"])
    return ret


def get_flag_emoji(code):
    """Returns a flag emoji, given a country code"""
    ret = ""
    for l in list(code):
        ret += unicodedata.lookup(f"regional indicator symbol letter {l}")

    return ret


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
    if shutil.get_terminal_size((0, 0)).columns >= 129 or not IS_TERMINAL:
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


class CacheDict(dict):
    timeout_hours = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__last_used_times: Dict[str, datetime] = {}

    def __getitem__(self, key):
        self.__last_used_times[key] = datetime.now()
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        self.__last_used_times[key] = datetime.now()
        super().__setitem__(key, value)

    def __delitem__(self, key):
        del self.__last_used_times[key]
        super().__delitem__(key)

    def clean(self) -> Dict[str, Any]:
        d = datetime.now()
        ret = {}
        for key, value in self.__last_used_times.items():
            if d - value > timedelta(hours=self.timeout_hours):
                ret[key] = self[key]
                del self[key]

        return ret
