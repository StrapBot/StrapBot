__version__ = "v4.0"

import asyncio
import discord
import dotenv
import json
import logging
import os
import pygit2
import random
import string
import sys
import traceback
import typing
from functools import partial
from inspect import iscoroutine
from pygit2.callbacks import RemoteCallbacks
from packaging.version import Version
from aiohttp import ClientSession
from collections import defaultdict
from discord.ext import commands, tasks
from typing import Union, Dict
from typing_extensions import Self
from discord import Message, Interaction
from concurrent.futures import ThreadPoolExecutor
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
    MarkovChain,
    load_chain_from_db,
    save_chain_to_db,
    CacheDict,
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
        # for git, we're going to use a different thread pool executor
        # because the git operations can be slow and we don't want them
        # to also slow down the other functions that may be running in
        # the default pool executor.
        self.__update_done = False
        self.__git_exec = ThreadPoolExecutor()
        self.__git_keypair = None
        self.__git_callbacks = None
        self.__markov_guild_operations = defaultdict(asyncio.Lock)
        self.__markov_loop_running = False
        self.__markov_chains: CacheDict[int, MarkovChain] = CacheDict()
        self.__git_lock = asyncio.Lock()
        self.__cached_configs: Dict[int, AnyConfig] = {}
        self._closing = False
        self.mongoclient: AgnosticClient
        self.mongodb: AgnosticDatabase
        self.session: ClientSession = None # type: ignore
        self.mongodb_uri = mongodb_uri
        self.webhook_url = webhook_url
        self.main_guild: typing.Optional[discord.Guild] = None
        self.use_repl = use_repl
        self.console = None
        self.markov_learn_events: typing.Dict[int, asyncio.Event] = {}

    @property
    def debugging(self) -> bool:
        return is_debugging()

    @property
    def version(self) -> str:
        return __version__

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

    async def get_latest_version(self) -> str:
        """Returns the latest version available on the git remote."""
        if not os.path.exists(".git"):
            return None

        def _do_fetch():
            self.__repo.remotes["origin"].fetch(callbacks=self.__git_callbacks)
            tags = [r for r in self.__repo.references if r.startswith("refs/tags/")]
            tags.sort(key=lambda tag: Version(tag.split("/")[-1]))

            latest_tag = tags[-1].split("/")[-1] if tags else None
            return latest_tag

        async with self.__git_lock:
            return await self.loop.run_in_executor(self.__git_exec, _do_fetch)

    async def check_for_updates(self) -> bool:
        """Check if the bot has available updates."""
        latest = await self.get_latest_version()

        return Version(latest) > Version(__version__)

    async def update(
        self, restart_if_pm2=True, *, yild=False, dbg=False
    ) -> Union[bool, typing.AsyncGenerator[str, None]]:
        """Download the bot updates."""
        if not await self.check_for_updates() or self.__update_done:
            if yild:
                yield "Already up to date."
            
            return

        m = "Getting updates..."
        logger.info(m)
        if yild:
            yield m

        ver = await self.get_latest_version()

        def _pull_and_checkout_to_ver():
            self.__repo.reset(self.__repo.head.target, pygit2.GIT_RESET_HARD)
            m = "Repository reset to HEAD."
            logger.debug(m)
            yield m

            self.__repo.remotes["origin"].fetch(callbacks=self.__git_callbacks)
            m = "Fetched the latest changes from the remote.\n"
            logger.debug(m)
            yield m

            remote = self.__repo.lookup_reference("refs/remotes/origin/main").target
            self.__repo.merge(remote)
            m = "Merged the changes with the local repository."
            logger.debug(m)
            yield m

            self.__repo.checkout(f"refs/tags/{ver}")
            m = f"Checked out to tag {ver}."
            logger.debug(m)
            yield m

        async with self.__git_lock:
            for m in await self.loop.run_in_executor(
                self.__git_exec, _pull_and_checkout_to_ver
            ):
                if yild and dbg:
                    yield m

            _, same_ip = await self.is_server_running()
            postupd = await asyncio.create_subprocess_shell(
                f"./tools/post-update.sh 1 {int(same_ip)}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _ = await postupd.communicate()
            if postupd.returncode != 0:
                raise RuntimeError(
                    f"An error occurred while running the post-update script:\n"
                    + stdout.decode()
                )

        if not same_ip:
            logger.warning("[bold blink red]Remember to also update the server![/]")
            if yild:
                yield "**Remember to also update the server!**"

        if "PM2_HOME" in os.environ:
            self._create_package_json(ver)
            if (
                not self._closing
                and restart_if_pm2
                and os.getenv("autorestart", "false") == "true"
            ):
                m = "Update downloaded, restarting..."
                logger.warning(m)
                if yild:
                    yield m

                await self.close()
        elif not self._closing:
            m = "Update downloaded. Restart to apply the changes."
            logger.info(m)
            if yild:
                yield m
            
        self.__update_done


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
        """Get a MongoDB collection."""
        name = dbname
        if cog:
            name = "cog." + name

        return self.mongodb[name]

    def get_cog_db(self, cog: commands.Cog):
        return self.get_db(type(cog).__name__, True)

    def _create_package_json(self, version=__version__):
        """Create or update a package.json file with the bot's version."""
        json.dump(
            {"version": version},
            open("package.json", "w"),
        )

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

        if os.path.exists(".git"):
            self.__repo = await self.loop.run_in_executor(
                self.__git_exec, pygit2.Repository, "."
            )
            self.__git_keypair = await self.loop.run_in_executor(
                self.__git_exec,
                pygit2.Keypair,
                "git",
                os.getenv("PUBKEY_PATH", f"{os.getenv('HOME')}/.ssh/id_rsa.pub"),
                os.getenv("PRIVKEY_PATH", f"{os.getenv('HOME')}/.ssh/id_rsa"),
                os.getenv("PRIVKEY_PASS", ""),
            )
            self.__git_callbacks = await self.loop.run_in_executor(
                self.__git_exec,
                partial(RemoteCallbacks, credentials=self.__git_keypair),
            )

        # PM2 compatibility
        if "PM2_HOME" in os.environ:
            if (
                not os.path.exists("package.json")
                or json.load(open("package.json"))["version"] != __version__
            ):
                self._create_package_json()
                logger.info(
                    "A [bold]package.json[/] file has been created "
                    "in the bot's directory to show the StrapBot "
                    "version in PM2. If the version changed, it may "
                    "display the wrong version until the bot is restarted."
                )

        # MongoDB
        # MongoDB database loading happens first because
        # some cogs might need the mongodb in the class
        mongodb = "[bold #4DB33D]MongoDB[/bold #4DB33D]"
        logger.debug(f"Connecting to {mongodb} database...")
        dbname = self.mongodb_uri.split("/")[-1]
        if "@" in dbname or ":" in dbname or not dbname:
            dbname = "strapbot"

        self.session = ClientSession(loop=self.loop)
        self.mongoclient = AsyncIOMotorClient(self.mongodb_uri, io_loop=self.loop)
        self.mongodb = self.mongoclient[dbname]
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
        if self.use_repl or self.debugging:
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

        # Loops
        self.markov_cache_loop.start()
        self.updates_loop.start()

        # Application commands
        main_guild_id = os.getenv("MAIN_GUILD_ID", None)
        logger.debug("Configuring command tree...")
        await self.tree.set_translator(MyTranslator())
        self._original_tree_error = self.tree.on_error
        self.tree.on_error = self.on_tree_error
        if main_guild_id != None and main_guild_id.isdigit():
            g = discord.Object(id=int(main_guild_id))
            self.tree.copy_global_to(guild=g)

    async def is_server_running(self) -> typing.Tuple[bool, bool]:
        """Check if the server is running."""
        chk = await self.check_youtube_news()
        same_ip = False
        if chk:
            internal = self.get_db("Internal", cog=False)
            data = await internal.find_one({"_id": "server"})
            if data:
                pub_ip = (
                    await (
                        await self.session.get("https://ifconfig.me/ip")
                    ).content.read()
                ).decode()
                same_ip = (
                    data.get("request_url", "a://a:a").split(":")[1].strip("/")
                    == pub_ip
                )

        return (chk, same_ip)

    async def check_youtube_news(self, log: bool = False):
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

    async def get_markov_chain(self, guild_id: int) -> typing.Optional[MarkovChain]:
        """Get the Markov chain for a guild."""
        chain = self.__markov_chains.get(guild_id, None)
        if chain:
            return chain

        async with self.__markov_guild_operations[guild_id]:
            chain = await load_chain_from_db(self.mongodb, guild_id)
            if chain is None:
                return

            self.__markov_chains[guild_id] = chain
            return chain

    async def save_markov_chain(self, guild_id: int):
        """Save the guild's Markov chain data."""
        chain = self.__markov_chains.pop(guild_id, None)
        if not chain:
            return

        async with self.__markov_guild_operations[guild_id]:
            try:
                await save_chain_to_db(self.mongodb, guild_id, chain)
            except Exception:
                self.__markov_chains[guild_id] = chain
                raise

    @tasks.loop(minutes=5)
    async def markov_cache_loop(self):
        """Loop to clear the Markov chains cache."""

        self.__markov_loop_running = True
        tasks = []

        for guild_id in self.__markov_chains.clean():
            await self.save_markov_chain(guild_id)

        if tasks:
            await asyncio.gather(*tasks)

        self.__markov_loop_running = False

    async def on_message(self, message: Message):
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        markov_cfg = ctx.guild_config.markov
        await self.process_commands(message)

        if (
            markov_cfg["enabled"]
            and not ctx.command
            and ctx.guild.id not in self.markov_learn_events
            and ctx.channel.id == markov_cfg["channel_id"]
        ):
            # because we don't want to learn one-word messages
            can_add = len(message.content.split(" ")) > 1

            min = markov_cfg["messages"]["min"]
            max = markov_cfg["messages"]["max"]
            db = self.get_db("MarkovChain", cog=False)
            data = await db.find_one({"_id": message.guild.id})
            if not data:
                return

            msg_set = data.pop("msg_set", random.randint(min, max))
            curr_msg = data.pop("curr_msg", msg_set)
            chain = await self.get_markov_chain(message.guild.id)
            if can_add:
                chain.add_message(message.content)

            if curr_msg >= msg_set:
                curr_msg = 1
                msg_set = random.randint(min, max)
                await message.channel.send(
                    chain.generate(markov_cfg["messages"]["words"]),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                curr_msg += 1

            await db.update_one(
                {"_id": message.guild.id},
                {
                    "$set": {
                        "msg_set": msg_set,
                        "curr_msg": curr_msg,
                    }
                },
                upsert=True,
            )

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
        await self.send_to_webhook(f"{msg}\n{eid}\n{ecl}\n{egs}")

    async def send_to_webhook(self, *args, **kwargs):
        wh = discord.Webhook.from_url(
            self.webhook_url,
            session=self.session,
            bot_token=self.http.token,
        )
        return await wh.send(*args, **kwargs)

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

    @tasks.loop(minutes=10)
    async def updates_loop(self):
        if await self.check_for_updates():
            pf = self.command_prefix
            if callable(pf):
                pf = pf(self, None)
                if iscoroutine(pf):
                    pf = await pf

            if isinstance(pf, list):
                pf = [
                    p
                    for p in pf
                    if p.strip() != self.user.mention
                    and p.strip() != f"<@!{self.user.id}>"
                ]
                pf = pf[0]

            msg = f"It's time to update! Run `{pf}update` to get the latest version."
            logger.info(msg)
            await self.send_to_webhook(msg)

            self.updates_loop.stop()

    async def close(self):
        self._closing = True
        if self.use_repl and not self.debugging and self.console:
            self.console.stop()

        if (
            self.markov_learn_events
            and any(not ev.is_set() for ev in self.markov_learn_events.values())
        ) or self.__markov_chains:
            evs = [e for e in self.markov_learn_events.values() if not e.is_set()]
            lng = len(evs)
            cnt = 0
            logger.info(
                f"[italic]Waiting for all the [green]Markov[/] events to finish...[/]"
            )
            logger.debug(f"[italic]Waiting for {lng} learning tasks to finish...[/]")
            s = "s" if lng != 1 else ""

            async def _task(ev):
                nonlocal cnt
                await ev.wait()
                cnt += 1
                lng = f"[bold green]{lng}[/]" if cnt == lng else lng
                outof = f" out of {lng}" if cnt != lng else ""
                logger.info(
                    f"[bold green]{cnt}[/]{outof} Markov learning event{s} finished."
                )

            tasks = [_task(ev) for ev in evs]

            if tasks:
                await asyncio.gather(*tasks)

            self.markov_cache_loop.stop()
            if self.__markov_loop_running:
                logger.debug("Waiting for the Markov cache loop to finish...")
                await self.markov_cache_loop.get_task()

            logger.info("Cleaning up...")
            if self.__markov_chains:
                await self.markov_cache_loop()

        a = True
        self.updates_loop.stop()
        while self.__git_lock.locked():
            if a:
                logger.info("Waiting for the git operations to finish...")
                a = False

            await asyncio.sleep(0.05)

        if self.session:
            await self.session.close()
        
        self.__git_exec.shutdown()
        return await super().close()


if __name__ == "__main__":
    dotenv.load_dotenv()
    for line in get_startup_text(__version__).splitlines():
        logger.info(line, extra={"highlighter": None})
        __import__("time").sleep(0.0035)

    token = raise_if_no_env("TOKEN", RuntimeError("A bot token is required."))
    mongodb = raise_if_no_env(
        "MONGO_URI", KeyError("A MongoDB database is required for the bot to work.")
    )
    webhook = raise_if_no_env(
        "ERRORS_WEBHOOK_URL", KeyError("A webhook URL for errors logging is required.")
    )
    use_repl = os.getenv("USE_REPL", "false").lower() in ["true", "1", "yes", "y", "on"]

    bot = StrapBot(
        mongodb_uri=mongodb, webhook_url=webhook, use_repl=use_repl and IS_TERMINAL
    )
    bot.run(token, log_handler=None)
