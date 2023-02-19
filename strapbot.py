import asyncio
import os
import random
import string
import sys
import traceback
import typing
import discord
import dotenv
from aiohttp import ClientSession
from discord.ext import commands
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import AnyConfig, Config
from core.context import StrapContext
from core.utils import (
    get_startup_text,
    raise_if_no_env,
    MyTranslator,
    configure_logging,
    get_logger,
)
from discord.ext.commands.bot import _default

configure_logging()
logger = get_logger()

dotenv.load_dotenv()


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
        self.mongoclient: AgnosticClient
        self.mongodb: AgnosticDatabase
        self.session: ClientSession
        self.mongodb_uri = mongodb_uri
        self.webhook_url = webhook_url

    def give_prefixes(self, bot, message: typing.Optional[discord.Message]):
        pfixes = [os.getenv("BOT_PREFIX", "sb.")]
        if message and not message.guild:
            pfixes.append("")

        return commands.when_mentioned_or(*pfixes)(bot, message)  # type: ignore

    async def get_config(
        self, target: typing.Union[discord.Guild, discord.User, discord.Member, int]
    ) -> typing.Optional[AnyConfig]:
        """Get a Config instance for a guild or user"""
        ret: typing.Union[discord.Guild, discord.User, None] = None
        if isinstance(target, int):
            ret = self.get_guild(target) or self.get_user(target)

        if isinstance(target, discord.Member):
            ret = self.get_user(target.id)  # must be User and not Member

        return await Config.create_config(self, ret or target)  #  type: ignore

    def get_db(self, dbname, cog=True):
        name = dbname
        if cog:
            name = "cog." + name

        return self.mongodb[name]

    async def setup_hook(self):

        # MongoDB
        # MongoDB database loading happens first because
        # some cogs might need the mongodb in the class
        mongodb = "[bold #4DB33D]MongoDB[/bold #4DB33D]"
        logger.debug(f"Connecting to {mongodb} database...")
        self.session = ClientSession(loop=self.loop)
        self.mongoclient = AsyncIOMotorClient(self.mongodb_uri)
        self.mongodb = self.mongoclient.strapbotrew
        await self.mongodb.command({"ping": 1})  # type: ignore
        logger.info(f"Connected to {mongodb} database.")

        # Extensions
        logger.debug("Loading extensions...")
        exts = set()
        for ext in os.listdir("cogs"):
            ext = os.path.splitext(ext)
            if ext[1] == ".py":
                exts.add(f"cogs.{ext[0]}")

        errors = 0
        for ext in exts:
            try:
                await self.load_extension(ext)
            except Exception as e:
                errors += 1
                e = getattr(e, "original", e)
                logger.error(f"Error loading [red bold]{ext}[/]", exc_info=e)

        additional = " with [bold]no errors[/]"
        if errors:
            additional = f", [bold]could not load[/] [bold red]{errors}[/] extension"
            additional += "s" if errors != 1 else ""

        logger.info(
            f"[bold green]{len(exts) - errors}[/] extensions loaded successfully{additional}.",
            extra={"highlighter": None},
        )

        # Application commands
        logger.debug("Configuring command tree...")
        g = discord.Object(id=746111972428480582)
        self._original_tree_error = self.tree.on_error
        await bot.tree.set_translator(MyTranslator())
        self.tree.copy_global_to(guild=g)
        await self.tree.sync(guild=g)

    async def on_ready(self):
        logger.info(
            f"[bold]StrapBot[/] successfully logged" f" in as [italic]{self.user}[/]!",
            extra={"highlighter": None},
        )

    async def get_context(self, message: discord.Message, /, *, cls=StrapContext):
        ctx = await super().get_context(message, cls=cls)
        ctx.config = await self.get_config(ctx.author)  # type: ignore
        ctx.guild_config = await self.get_config(ctx.guild)  # type: ignore
        return ctx

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

    async def on_error(self, meth: str, *args, **kwargs):
        exc = sys.exc_info()[1]
        await super().on_error(meth, *args, **kwargs)
        await self.handle_errors(exc, meth, "method")  # type: ignore

    async def on_command_error(self, ctx: StrapContext, exc: commands.CommandError):
        while hasattr(exc, "original"):
            exc = exc.original  #  type: ignore
            await asyncio.sleep(0.1)

        await super().on_command_error(ctx, exc)
        if isinstance(exc, commands.CommandNotFound):
            return  # placeholder

        await self.handle_errors(exc, ctx.command.qualified_name, "command")  # type: ignore

    async def close(self):
        await self.session.close()
        return await super().close()


if __name__ == "__main__":
    for line in get_startup_text("v4 alpha").splitlines():
        logger.info(line, extra={"highlighter": None})

    token = raise_if_no_env("TOKEN", RuntimeError("A bot token is required."))
    mongodb = raise_if_no_env(
        "MONGO_URI", KeyError("A MongoDB database is required for the bot to work.")
    )
    webhook = raise_if_no_env(
        "ERRORS_WEBHOOK_URL", KeyError("A webhook URL for errors logging is required.")
    )

    bot = StrapBot(mongodb_uri=mongodb, webhook_url=webhook)
    bot.run(token, log_handler=None)
