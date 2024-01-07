import asyncio
import os
import random
import string
import sys
import traceback
import typing
import discord
import dotenv
import logging
from aiohttp import ClientSession
from discord.ext import commands
from typing import Union, Dict
from typing_extensions import Self
from discord import Message, Interaction
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import AnyConfig, Config, UserConfig, GuildConfig
from core.context import StrapContext
from core.utils import (
    IS_TERMINAL,
    HANDLER as logging_handler,
    get_startup_text,
    raise_if_no_env,
    configure_logging,
    get_logger,
    MyTranslator,
    is_debugging,
)
from discord.ext.commands.bot import _default
from core.repl import InteractiveConsole, REPLThread

if is_debugging():
    from core.utils import get_debug_eval_in_loop_class, get_debug_evaluate_expression

configure_logging()
logger = get_logger()


class StrapBot(commands.Bot):
    def __init__(
        self,
        command_prefix=None,
        *,
        mongodb_uri: str,
        webhook_url: str,
        help_command: typing.Optional[commands.HelpCommand] = _default,
        tree_cls: typing.Type[
            discord.app_commands.CommandTree[typing.Any]
        ] = discord.app_commands.CommandTree,
        description: typing.Optional[str] = None,
        intents: discord.Intents = discord.Intents.all(),
        allowed_mentions: typing.Optional[
            discord.AllowedMentions
        ] = discord.AllowedMentions.none(),
        use_repl: bool = False,
        **options: typing.Any,
    ):
        super().__init__(
            command_prefix or self.give_prefixes,
            help_command=help_command,
            tree_cls=tree_cls,
            description=description,
            intents=intents,
            allowed_mentions=allowed_mentions,
            **options,
        )
        self.__cached_configs: Dict[int, AnyConfig] = {}
        self.mongoclient: AgnosticClient
        self.mongodb: AgnosticDatabase
        self.session: ClientSession
        self.mongodb_uri = mongodb_uri
        self.webhook_url = webhook_url
        self.main_guild: typing.Optional[discord.Guild] = None
        self.use_repl = use_repl

    @property
    def debugging(self) -> bool:
        return is_debugging()

    def do_give_prefixes(
        self, bot, message: typing.Optional[Message]
    ) -> typing.List[str]:
        p = os.getenv("BOT_PREFIX", "sb.").strip()
        p = p if p else "sb."
        pfixes = [p]
        if message and not message.guild:
            pfixes.append("")

        return pfixes

    def give_prefixes(self, bot, message: typing.Optional[Message]) -> typing.List[str]:
        p = self.do_give_prefixes(bot, message)
        return commands.when_mentioned_or(*p)(bot, message)  # type: ignore

    def get_cached_config(self, id: int):
        if id in self.__cached_configs:
            return self.__cached_configs[id]

    async def get_config(
        self, target: typing.Union[discord.Guild, discord.User, discord.Member, int]
    ) -> AnyConfig:
        """Get a Config instance for a guild or user"""
        if not isinstance(target, int):
            id = target.id

        cfg = self.get_cached_config(id)
        if not cfg:
            ret: typing.Union[discord.Guild, discord.User, None] = None
            if isinstance(target, int):
                ret = self.get_guild(target) or self.get_user(target)

            if isinstance(target, discord.Member):
                ret = self.get_user(target.id)  # must be User and not Member

            cfg = await Config.create_config(self, ret or target)  #  type: ignore
            self.__cached_configs[id] = cfg

        return cfg

    def get_db(self, dbname, cog=True):
        name = dbname
        if cog:
            name = "cog." + name

        return self.mongodb[name]

    def get_cog_db(self, cog: commands.Cog):
        return self.get_db(type(cog).__name__, True)

    async def setup_hook(self):
        """Various startup configurations."""
        if __name__ == "__main__":
            # remove variables that are not needed anymore
            global token
            global webhook
            global mongodb
            del token
            del webhook
            del mongodb

        # MongoDB
        # MongoDB database loading happens first because
        # some cogs might need the mongodb in the class
        mongodb = "[bold #4DB33D]MongoDB[/bold #4DB33D]"
        logger.debug(f"Connecting to {mongodb} database...")
        self.session = ClientSession(loop=self.loop)
        self.mongoclient = AsyncIOMotorClient(self.mongodb_uri, io_loop=self.loop)
        self.mongodb = self.mongoclient.strapbotrew
        await self.mongodb.command({"ping": 1})  # type: ignore

        cache = self.get_db("Cache", cog=False)

        # NOTE: at the first startup of the bot, the Cache collection
        #       doesn't exist, so its indexes don't exist too.
        if not await cache.list_indexes().to_list(None):
            # 172800s = 48h
            # TODO: maybe put the cache expiration in an environment variable
            await cache.create_index(
                "used_at", name="ClearIndex", expireAfterSeconds=172800
            )  #  type: ignore
            await cache.create_index(
                "query", name="QueriesIndex", unique=True
            )  #  type: ignore

        logger.info(f"Connected to {mongodb} database.")

        # REPL and debugging
        if self.use_repl:
            if self.debugging:
                self.use_repl = False
                # modify pydevd to have the bot and its loop inside its debug console
                _vars = sys.modules["_pydevd_bundle"].pydevd_vars
                self._original_eval_exp = _vars.evaluate_expression
                self._original_eval_class = _vars._EvalAwaitInNewEventLoop
                _vars.evaluate_expression = get_debug_evaluate_expression(self)
                _vars._EvalAwaitInNewEventLoop = get_debug_eval_in_loop_class(self)
            else:
                try:
                    import readline
                except ImportError:
                    pass
                repl_locals = {"asyncio": asyncio, "bot": self}
                repl_locals.update(globals())
                self.console = InteractiveConsole(repl_locals, self, self.loop)
                logging_handler.iconsole = self.console  # type: ignore
                self.repl_thread = REPLThread(self)
                self.repl_thread.daemon = True

        # Extensions
        logger.debug("Loading extensions...")
        exts = set()
        cexts = set()
        for ext in os.listdir("cogs"):
            ext = os.path.splitext(ext)
            if ext[1] == ".py":
                exts.add(f"cogs.{ext[0]}")

        if os.path.exists("custom/cogs"):
            for ext in os.listdir("custom/cogs"):
                ext = os.path.splitext(ext)
                if ext[1] == ".py":
                    cexts.add(f"custom.cogs.{ext[0]}")

        errors = 0
        cerrors = 0
        for ext in set(list(exts) + list(cexts)):
            custom = ext in cexts
            text = "custom extension" if custom else "extension"
            try:
                await self.load_extension(ext)
            except Exception as e:
                if custom:
                    cerrors += 1
                else:
                    errors += 1
                e = getattr(e, "original", e)
                logger.error(f"Error loading {text} [red bold]{ext}[/]", exc_info=e)
            else:
                logger.debug(f"{text.capitalize()} [bold]{ext}[/] loaded successfully.")

        additional = " with [bold]no errors[/]"
        if errors:
            additional = f", [bold]could not load[/] [bold red]{errors}[/] extension"
            additional += "s" if errors != 1 else ""

        if cerrors:
            if errors:
                additional += " and "
            else:
                additional += ", [bold]could not load[/] "
            
            additional += f"[bold red]{cerrors}[/] custom extension"
            additional += "s" if cerrors != 1 else ""

        loaded = len(exts) - errors
        cloaded = len(cexts) - cerrors
        c = "s" if loaded != 1 else ""
        if cexts:
            c += f" and [bold green]{cloaded}[/] custom extension"
            c += "s" if cloaded != 1 else ""


        logger.info(
            f"[bold green]{loaded}[/] extension{c} loaded successfully{additional}.",
            extra={"highlighter": None},
        )

        # YouTube news
        # It would have taken too long to start the bot in some cases
        self.loop.create_task(self.check_youtube_news(True))

        # Application commands
        main_guild_id = os.getenv("MAIN_GUILD_ID", None)
        logger.debug("Configuring command tree...")
        await self.tree.set_translator(MyTranslator())
        self._original_tree_error = self.tree.on_error
        self.tree.on_error = self.on_tree_error
        if main_guild_id != None and main_guild_id.isdigit():
            g = discord.Object(id=int(main_guild_id))
            self.tree.copy_global_to(guild=g)

    async def check_youtube_news(self, log: bool = False) -> bool:
        """
        Function that checks if the YouTube news
        server has been configured and is running.
        """

        def _maybe_log(level, *args, **kwargs):
            if log:
                logger.log(level, *args, **kwargs)

        _maybe_log(logging.DEBUG, "Checking if the server is running...")
        internal = self.get_db("Internal", cog=False)
        data = await internal.find_one({"_id": "server"})  #  type: ignore
        yt_msg = "The server hasn't been set up yet. YouTube news will not work."
        if data == None or (data and data.get("request_url", None) == None):
            _maybe_log(logging.WARNING, yt_msg)
            return False
        elif data and data.get("request_url") != None:
            chg = list(str(random.randint(0, 10000000000000000000)))
            if len(chg) >= 3:
                bpos = random.randint(0, len(chg) - 1)
                opos = random.randint(0, len(chg) - 1)
                while opos == bpos:
                    opos = random.randint(0, len(chg) - 1)

                tpos = random.randint(0, len(chg) - 1)
                while tpos == bpos or tpos == opos:
                    tpos = random.randint(0, len(chg) - 1)

                chg[bpos] = "b"
                chg[opos] = "o"
                chg[tpos] = "t"

            chg = "".join(chg)
            try:
                async with self.session.get(
                    data["request_url"] + "/notify", params={"hub.challenge": chg}
                ) as req:
                    if (await req.content.read()).decode() != chg or (
                        req.status < 200 or req.status >= 300
                    ):
                        _maybe_log(logging.WARNING, yt_msg)
                        return False
            except Exception:
                _maybe_log(
                    logging.WARNING,
                    "The server might be down. Check if it's running for YouTube news to work.",
                )
                return False

        return True

    async def request_pubsubhubbub(
        self, channel_id: str, subscribe: bool, raise_for_status: bool = True
    ):
        """Sends a request to Google's PubSubHubbub Hub."""
        assert await self.check_youtube_news(), "The server is down."
        internal = self.get_db("Internal", cog=False)
        serverdata = await internal.find_one({"_id": "server"})  #  type: ignore
        data = {
            "hub.callback": f"{serverdata['request_url']}/notify",
            "hub.topic": f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}",
            "hub.verify": "sync",
            "hub.mode": f"{'un' if not subscribe else ''}subscribe",
            "hub.verify_token": "",
            "hub.secret": "",
            "hub.lease_seconds": "",
        }
        async with self.session.post(
            "https://pubsubhubbub.appspot.com/subscribe", data=data
        ) as resp:
            if raise_for_status:
                resp.raise_for_status()

    async def on_ready(self):
        logger.info(
            f"[bold]StrapBot[/] successfully logged" f" in as [italic]{self.user}[/]!",
            extra={"highlighter": None},
        )
        main_guild_id = os.getenv("MAIN_GUILD_ID", None)
        if main_guild_id != None and main_guild_id.isdigit():
            self.main_guild = self.get_guild(int(main_guild_id))

        if self.use_repl and not self.debugging:
            self.repl_thread.start()

    async def get_context(
        self, origin: Union[Message, Interaction[Self]], /, *, cls=StrapContext
    ):
        if not issubclass(cls, StrapContext):
            raise TypeError("context class must inherit from StrapContext")

        if isinstance(origin, Interaction):
            author = origin.user
        else:
            author = origin.author

        user_config: UserConfig = await self.get_config(author)  #  type: ignore
        guild_config: GuildConfig = await self.get_config(origin.guild)  # type: ignore
        return await super().get_context(
            origin, cls=cls.configure(user_config, guild_config)
        )

    @staticmethod
    def create_random_string(length=10):
        """Creates a string with random characters."""
        symbols = list(string.ascii_letters + string.digits)
        return "".join([random.choice(symbols) for _ in range(length)])

    async def handle_errors(
        self, exc: BaseException, event: typing.Any = "", event_type: str = ""
    ):
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        db: AgnosticCollection = self.mongodb.Errors
        _id = self.create_random_string()
        try:
            while await db.find_one({"_id": _id}):  # type: ignore
                await asyncio.sleep(0.1)
                _id = self.create_random_string()
        except Exception:
            pass

        args = "\n - " + "\n - ".join([f"`{a}`" for a in exc.args])
        if len(args) >= 1000:
            args = None

        if not list(exc.args):
            args = False

        msg = "An exception occurred"
        if event and event_type:
            msg += f" in {event_type} `{event}`"
        elif event_type and not event:
            a = "a" if not event_type.lower().startswith(tuple("aeiou")) else "an"
            msg += f" in {a} {event_type}"

        msg += "."

        try:
            await db.insert_one(  # type: ignore
                {
                    "_id": _id,
                    "traceback": tb,
                    "class": type(exc).__name__,
                    "args": list(exc.args),
                    "event": event,
                    "type": event_type,
                }
            )
        except Exception:
            _id = None

        wh = discord.Webhook.from_url(
            self.webhook_url,
            session=self.session,
            bot_token=self.http.token,
        )
        eid = f"Error ID: `{_id}`" if _id else "Couldn't store data in database."
        ecl = f"Error class: `{exc.__class__.__name__}`"
        egs = (
            f"Error args: {args}"
            if args
            else (
                "Couldn't send args, list would be longer than 1000 chars."
                if args == None
                else ""
            )
        )
        await wh.send(f"{msg}\n{eid}\n{ecl}\n{egs}")

    async def on_tree_error(
        self,
        interaction: Interaction[Self],
        error: discord.app_commands.AppCommandError,
        /,
    ) -> None:
        await self._original_tree_error(interaction, error)  #  type: ignore
        await self.handle_errors(error, interaction.namespace, "interaction")

    async def on_error(self, meth: str, *args, **kwargs):
        exc = sys.exc_info()[1]
        await super().on_error(meth, *args, **kwargs)
        await self.handle_errors(exc, meth, "method")  # type: ignore

    async def on_command_error(self, ctx: StrapContext, exc: commands.CommandError):
        while hasattr(exc, "original"):
            exc = exc.original  #  type: ignore

        await super().on_command_error(ctx, exc)
        if isinstance(exc, commands.CommandNotFound):
            return  # placeholder

        await self.handle_errors(exc, ctx.command.qualified_name, "command")  # type: ignore

    async def close(self):
        if self.use_repl and not self.debugging:
            self.console.stop()
        await self.session.close()
        return await super().close()


if __name__ == "__main__":
    dotenv.load_dotenv()
    for line in get_startup_text("v4 beta").splitlines():
        logger.info(line, extra={"highlighter": None})
        __import__("time").sleep(0.0035)

    token = raise_if_no_env("TOKEN", RuntimeError("A bot token is required."))
    mongodb = raise_if_no_env(
        "MONGO_URI", KeyError("A MongoDB database is required for the bot to work.")
    )
    webhook = raise_if_no_env(
        "ERRORS_WEBHOOK_URL", KeyError("A webhook URL for errors logging is required.")
    )

    bot = StrapBot(mongodb_uri=mongodb, webhook_url=webhook, use_repl=IS_TERMINAL)
    bot.run(token, log_handler=None)
