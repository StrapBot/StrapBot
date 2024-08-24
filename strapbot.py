__version__ = "v4.1.0"

import asyncio
import json
import logging
import os
import random
import string
import sys
import tempfile
import traceback
import typing
from typing import Union, Dict, Optional, List
from functools import partial
from inspect import iscoroutine
from collections import defaultdict
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor

import discord
import dotenv
import pygit2
from discord import Message, Interaction
from discord.ext import commands, tasks
from discord.ext.commands.bot import _default
from discord.utils import _is_submodule
from pygit2.callbacks import RemoteCallbacks
from packaging.version import Version
from aiohttp import ClientSession
from typing_extensions import Self
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient
from core.repl import InteractiveConsole, REPLThread
from core.config import AnyConfig, Config, UserConfig, GuildConfig
from core.context import StrapContext
from core.utils import (
    IS_TERMINAL,
    EXT_NAME,
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
    find_requirements,
    custom_ext_from_code,
    upload_code_to_db,
    get_ext_from_db,
    ReviewStatus,
)

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
        help_command: Optional[commands.HelpCommand] = _default,
        tree_cls: typing.Type[
            discord.app_commands.CommandTree[typing.Any]
        ] = discord.app_commands.CommandTree,
        description: Optional[str] = None,
        intents: discord.Intents = discord.Intents.all(),
        allowed_mentions: Optional[
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
        # for git, we're going to use a different thread pool executor
        # because the git operations can be slow and we don't want them
        # to also slow down the other functions that may be running in
        # the default pool executor.
        self.__update_done = False
        self.__git_exec = ThreadPoolExecutor()
        self.__git_keypair = None
        self.__git_callbacks = None
        self.__markov_guild_operations = defaultdict(asyncio.Lock)
        self.__markov_loop_running = False
        self.__markov_chains = CacheDict()
        self.__git_lock = asyncio.Lock()
        self.__cached_configs: Dict[int, AnyConfig] = {}
        self._closing = False
        self.mongoclient: AgnosticClient
        self.mongodb: AgnosticDatabase
        self.session: ClientSession = None  # type: ignore
        self.mongodb_uri = mongodb_uri
        self.webhook_url = webhook_url
        self.main_guild: Optional[discord.Guild] = None
        self.use_repl = use_repl
        self.console = None
        self.markov_learn_events: typing.Dict[int, asyncio.Event] = {}
        self.custom_commands: Dict[int, Dict[str, commands.Command]] = defaultdict(dict)
        self.custom_cogs: Dict[int, commands.Cog] = {}
        self.custom_cogs_errors: Dict[int, dict] = defaultdict(dict)

    # ===== Properties =====

    @property
    def debugging(self) -> bool:
        return is_debugging()

    @property
    def version(self) -> str:
        return __version__

    def do_give_prefixes(self, bot, message: Optional[Message]) -> List[str]:
        p = os.getenv("BOT_PREFIX", "sb.").strip()
        p = p if p else "sb."
        pfixes = [p]
        if message and not message.guild:
            pfixes.append("")

        return pfixes

    def give_prefixes(self, bot, message: Optional[Message]) -> List[str]:
        p = self.do_give_prefixes(bot, message)
        return commands.when_mentioned_or(*p)(bot, message)  # type: ignore

    # ===== Config and DB =====

    def get_cached_config(self, id: int):
        if id in self.__cached_configs:
            return self.__cached_configs[id]

    async def get_config(
        self, target: typing.Union[discord.Guild, discord.User, discord.Member, int]
    ) -> AnyConfig:
        """Get a Config instance for a guild or user"""
        if not isinstance(target, int):
            id_ = target.id

        cfg = self.get_cached_config(id_)
        if not cfg:
            ret: typing.Union[discord.Guild, discord.User, None] = None
            if isinstance(target, int):
                ret = self.get_guild(target) or self.get_user(target)

            if isinstance(target, discord.Member):
                ret = self.get_user(target.id)  # must be User and not Member

            cfg = await Config.create_config(self, ret or target)  #  type: ignore
            self.__cached_configs[id_] = cfg

        return cfg

    def get_db(self, dbname, cog=True):
        """Get a MongoDB collection."""
        name = dbname
        if cog:
            name = "cog." + name

        return self.mongodb[name]

    def get_cog_db(self, cog: commands.Cog):
        return self.get_db(type(cog).__name__, True)

    # ===== Updater =====

    async def get_latest_version(self) -> Optional[str]:
        """Returns the latest version available on the git remote."""
        if not os.path.exists(".git"):
            return None

        def _do_fetch():
            self.__repo.remotes["origin"].fetch(callbacks=self.__git_callbacks)
            tags: List[str] = [r for r in self.__repo.references if r.startswith("refs/tags/")]  # type: ignore
            tags.sort(key=lambda tag: Version(tag.split("/")[-1]))

            latest_tag = tags[-1].split("/")[-1] if tags else None
            return latest_tag

        async with self.__git_lock:
            return await self.loop.run_in_executor(self.__git_exec, _do_fetch)

    async def check_for_updates(self) -> bool:
        """Check if the bot has available updates."""
        latest = await self.get_latest_version()
        if not latest:
            return False

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

        ver: str = await self.get_latest_version()  # type: ignore

        def _pull_and_checkout_to_ver(
            repo: pygit2.Repository = self.__repo, chko=ver, is_commit=False
        ):
            repo.reset(
                repo.head.target,
                pygit2.GIT_RESET_HARD,  #  pylint: disable=no-member  # type: ignore
            )
            m = "Repository reset to HEAD."
            logger.debug(m)
            yield m

            repo.remotes["origin"].fetch(callbacks=self.__git_callbacks)
            m = "Fetched the latest changes from the remote.\n"
            logger.debug(m)
            yield m

            remote = repo.lookup_reference("refs/remotes/origin/main").target
            repo.merge(remote)
            m = "Merged the changes with the local repository."
            logger.debug(m)
            yield m

            if is_commit:
                comm = repo.get(chko)
                repo.checkout_tree(comm)  # type: ignore
                repo.set_head(comm.id)  # type: ignore
                m = f"Checked out to commit `{chko}`."
            else:
                repo.checkout(f"refs/tags/{chko}")
                m = f"Checked out to {chko}."

            logger.debug(m)
            yield m
            # perform another reset to remove merge conflicts
            repo.reset(
                repo.head.target,
                pygit2.GIT_RESET_HARD,  #  pylint: disable=no-member  # type: ignore
            )

            # because it's not gonna happen automatically,
            # and there's no easier way to pull the submodules
            # like we would do with `git pull --recurse-submodules`,
            # we're gonna do it manually.
            for sub in repo.submodules:
                m = f"Updating submodule {sub.name}..."
                logger.debug(m)
                yield m
                tmp_repo = pygit2.Repository(os.path.join(repo.workdir, sub.path))
                for ms in _pull_and_checkout_to_ver(tmp_repo, str(sub.head_id), True):
                    yield ms

                del tmp_repo
                m = f"Submodule {sub.name} updated."
                logger.debug(m)
                yield m

        v = sys.version_info
        ver = f"{v.major}.{v.minor}"
        async with self.__git_lock:
            for m in await self.loop.run_in_executor(
                self.__git_exec, _pull_and_checkout_to_ver
            ):
                if yild and dbg:
                    yield m

            _, same_ip = await self.is_server_running()
            postupd = await asyncio.create_subprocess_shell(
                f"./tools/post-update.sh 1 {int(same_ip)} {ver}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _ = await postupd.communicate()
            if postupd.returncode != 0:
                raise RuntimeError(
                    "An error occurred while running the post-update script:\n"
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

        self.__update_done = True

    def _create_package_json(self, version=__version__):
        """Create or update a package.json file with the bot's version."""
        json.dump(
            {"version": version},
            open("package.json", "w"),
        )

    @tasks.loop(minutes=10)
    async def updates_loop(self):
        if await self.check_for_updates():
            pf = self.command_prefix
            if callable(pf):
                pf = pf(self, None)  # type: ignore
                if iscoroutine(pf):
                    pf = await pf

            if isinstance(pf, list):
                if self.user:
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

    # ===== Startup tasks =====

    async def setup_hook(self):
        """Various startup configurations."""
        if __name__ == "__main__":
            # remove variables that are not needed anymore
            global token
            global webhook
            global mongodb
            del token  # pylint: disable=undefined-variable
            del webhook  # pylint: disable=undefined-variable
            del mongodb  # pylint: disable=undefined-variable

        # ==== REPL and debugging ====
        if self.use_repl or self.debugging:
            if self.debugging:
                self.use_repl = False
                # modify pydevd to have the bot and its loop inside its debug console
                _vars = sys.modules["_pydevd_bundle"].pydevd_vars

                self._original_eval_exp = _vars.evaluate_expression
                self._original_eval_class = (
                    _vars._EvalAwaitInNewEventLoop  # pylint: disable=protected-access
                )
                _vars.evaluate_expression = get_debug_evaluate_expression(self)
                _vars._EvalAwaitInNewEventLoop = (  # pylint: disable=protected-access
                    get_debug_eval_in_loop_class(self)
                )
            else:
                try:
                    import readline  # pylint: disable=all
                except ImportError:
                    pass
                repl_locals = {"asyncio": asyncio, "bot": self}
                repl_locals.update(globals())
                self.console = InteractiveConsole(repl_locals, self, self.loop)
                logging_handler.iconsole = self.console  # type: ignore
                self.repl_thread = REPLThread(self)
                self.repl_thread.daemon = True

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

        # ==== PM2 compatibility ====
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

        # ==== MongoDB ====
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

        # ==== Extensions ====
        logger.debug("Loading extensions...")
        exts = set()
        cexts = set()
        gexts = set()
        for ext in os.listdir("cogs"):
            ext = os.path.splitext(ext)
            if ext[1] == ".py":
                exts.add(f"cogs.{ext[0]}")

        if os.path.exists("custom/cogs"):
            for ext in os.listdir("custom/cogs"):
                ext = os.path.splitext(ext)
                if ext[1] == ".py":
                    cexts.add(f"custom.cogs.{ext[0]}")

        entries = await self.get_db("CustomCogs", cog=False).find().to_list(None)

        for entry in entries:
            if entry.get("status", "") == ReviewStatus.ok.value:
                gexts.add(entry["_id"])

        errors = 0
        cerrors = 0
        gerrors = 0

        async def _load(ext):
            nonlocal errors, cerrors, gerrors
            custom = ext in cexts
            guild = ext in gexts
            text = "custom extension" if custom else "extension"
            text = "guild extension" if guild else text
            try:
                await self.load_extension(ext)
            except Exception as e:
                if custom:
                    cerrors += 1
                elif guild:
                    gerrors += 1
                else:
                    errors += 1
                e = getattr(e, "original", e)
                logger.error(f"Error loading {text} [red bold]{ext}[/]", exc_info=e)
            else:
                logger.debug(f"{text.capitalize()} [bold]{ext}[/] loaded successfully.")

        tasks = []
        for ext in set(list(exts) + list(cexts)):
            tasks.append(_load(ext))

        await asyncio.gather(*tasks)

        if gexts:
            logger.debug("Loading guild extensions...")
            tasks = []
            for ext in set(gexts):
                tasks.append(_load(ext))

            await asyncio.gather(*tasks)

        additional = " with [bold]no errors[/]"
        if errors:
            additional = f", [bold]could not load[/] [bold red]{errors}[/] extension"
            additional += "s" if errors != 1 else ""

        if cerrors:
            if gerrors:
                additional += ", "
            elif errors:
                additional += " and "
            else:
                additional += ", [bold]could not load[/] "

            additional += f"[bold red]{cerrors}[/] custom extension"
            additional += "s" if cerrors != 1 else ""

        if gerrors:
            if errors or cerrors:
                additional += " and "
            else:
                additional += ", [bold]could not load[/] "

            additional += f"[bold red]{gerrors}[/] guild extension"
            additional += "s" if gerrors != 1 else ""

        loaded = len(exts) - errors
        cloaded = len(cexts) - cerrors
        gloaded = len(gexts) - gerrors
        c = "s" if loaded != 1 else ""
        if cloaded:
            if gloaded:
                c += ","
            else:
                c += " and"

            c += f" [bold green]{cloaded}[/] custom extension"
            c += "s" if cloaded != 1 else ""

        if gloaded:
            c += f" and [bold green]{gloaded}[/] guild extension"
            c += "s" if gloaded != 1 else ""

        logger.info(
            f"[bold green]{loaded}[/] extension{c} loaded successfully{additional}.",
            extra={"highlighter": None},
        )

        # ==== YouTube news ====
        # It would have taken too long to start the bot in some cases
        self.loop.create_task(self.check_youtube_news(True))

        # ==== Loops ====
        self.markov_cache_loop.start()
        self.updates_loop.start()
        self.clear_errors_loop.start()

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
                req_url = data.get("request_url", "a://a:a")
                same_ip = req_url.split(":")[1].strip(
                    "/"
                ) == pub_ip or req_url == os.getenv("SERVER_REQUEST_URl", "b://b:b")

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
        if not serverdata:
            raise RuntimeError("The server hasn't been set up yet.")

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
            f"[bold]StrapBot[/] successfully logged in as [italic]{self.user}[/]!",
            extra={"highlighter": None},
        )
        main_guild_id = os.getenv("MAIN_GUILD_ID", None)
        if main_guild_id != None and main_guild_id.isdigit():
            self.main_guild = self.get_guild(int(main_guild_id))

        if self.use_repl and not self.debugging:
            self.repl_thread.start()

    # ===== Commands and error handling =====

    async def on_message(self, message: Message):
        if message.author.bot:
            return

        await self.process_commands(message)

        ctx = await self.get_context(message)
        if (
            message.guild
            and ctx.guild  # because the linter will keep complaining
            and ctx.guild_config.markov["enabled"]
            and not ctx.command
            and ctx.guild.id not in self.markov_learn_events
            and ctx.channel.id == ctx.guild_config.markov["channel_id"]
        ):
            markov_cfg = ctx.guild_config.markov
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
            chain: MarkovChain = await self.get_markov_chain(
                message.guild.id
            )  #  type: ignore
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

        ctx = await super().get_context(
            origin, cls=cls.configure(user_config, guild_config)
        )

        if ctx.guild and not ctx.command and ctx.invoked_with:
            ctx.command = self.custom_commands[ctx.guild.id].get(ctx.invoked_with)

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

        if getattr(ctx.cog, "guild_id", None) is None:
            await super().on_command_error(ctx, exc)

        if isinstance(exc, commands.CommandNotFound):
            return  # placeholder

        # we don't want to know about the errors that are raised
        # by custom commands, as whoever made the extension must
        # debug it correctly.
        if ctx.guild and getattr(ctx.cog, "guild_id", None) == ctx.guild.id:
            count = self.custom_cogs_errors[ctx.guild.id].get("count", 0)
            self.custom_cogs_errors[ctx.guild.id] = {
                "count": count + 1,
                "last_time": datetime.now(),
            }
            if count >= 5:
                await ctx.send(
                    "Too many errors within 15 minutes. "
                    "The custom commands have been disabled.\n"
                    "If you are the developer of those commands, "
                    "please fix the issues and request an update."
                )
                await self.unload_extension(ctx.guild.id)
                await self.set_ext_status(ctx.guild.id, ReviewStatus.errored)
                return

            await ctx.send(
                "An error occurred while executing the custom command. Has the code been debugged correctly?"
            )
        else:
            await self.handle_errors(exc, ctx.command.qualified_name, "command")  # type: ignore

    # ===== Custom extensions =====

    @tasks.loop(minutes=15)
    async def clear_errors_loop(self):
        for guild_id, data in self.custom_cogs_errors.items():
            if (
                data.get("count", 0) < 5
                and (datetime.now() - data.get("last_time", datetime.now())).seconds
                >= 900
            ):
                self.custom_cogs_errors.pop(guild_id)

    def add_command(self, command: commands.Command):
        """
        Add a command to the bot.

        This method is overridden to add support for custom commands,
        which only work in specified guilds.
        """
        if (
            command.cog
            and hasattr(command.cog, "guild_id")
            and command.cog.guild_id is not None
        ):
            guild_id = command.cog.guild_id
            _cmd_exists = (
                lambda cmd: cmd in self.all_commands
                or cmd in self.custom_commands[guild_id]
            )

            if _cmd_exists(command.name):
                raise commands.CommandRegistrationError(command.name)

            self.custom_commands[guild_id][command.name] = command
            for alias in command.aliases:
                if _cmd_exists(alias):
                    self.remove_command(command.name, guild_id)
                    raise commands.CommandRegistrationError(alias, alias_conflict=True)

                self.custom_commands[guild_id][alias] = command

            if (
                isinstance(command, (commands.HybridCommand, commands.HybridGroup))
                and command.app_command
                and not command.cog.__cog_is_app_commands_group__
            ):
                self.tree.add_command(
                    command.app_command, guild=discord.Object(id=guild_id)
                )

            return

        return super().add_command(command)

    def remove_command(self, name: str, guild_id: Optional[int] = None):
        """
        Remove a command from the bot.

        This method is overridden to add support for custom commands,
        which only work in specified guilds.

        NOTE: You must provide the guild_id if you want to remove a custom command.
        """
        if guild_id:
            command = self.custom_commands[guild_id].pop(name, None)
            if command == None:
                return

            if name in command.aliases:
                return command

            for alias in command.aliases:
                cmd = self.custom_commands[guild_id].pop(alias, None)
                if cmd != None and cmd != command:
                    self.custom_commands[guild_id][alias] = cmd

            if (
                isinstance(command, (commands.HybridCommand, commands.HybridGroup))
                and command.app_command
            ):
                if command.cog.__cog_is_app_commands_group__:
                    return cmd

                self.tree.remove_command(name, guild=discord.Object(id=guild_id))

            return command

        return super().remove_command(name)

    async def add_cog(
        self,
        cog: commands.Cog,
        /,
        *,
        override: bool = False,
        guild: Optional[discord.abc.Snowflake] = discord.utils.MISSING,
        guilds: typing.Sequence[discord.abc.Snowflake] = discord.utils.MISSING,
    ) -> None:
        """
        Add a cog to the bot.

        This method is overridden to add support for custom cogs,
        which only work in specified guilds.
        """
        if hasattr(cog, "guild_id") and cog.guild_id is not None:  # type: ignore
            g_id: int = cog.guild_id  # type: ignore
            existing = self.custom_cogs.get(g_id)

            if existing is not None:
                if not override:
                    raise discord.ClientException(
                        f"A custom cog for guild {g_id} already exists."
                    )

                await self.remove_cog(g_id)

            if cog.__cog_app_commands_group__:
                self.tree.add_command(
                    cog.__cog_app_commands_group__,
                    override=override,
                    guild=discord.Object(id=g_id),
                )

            cog = await cog._inject(self, override=override, guild=guild, guilds=guilds)
            self.custom_cogs[g_id] = cog
            return

        return await super().add_cog(cog, override=override, guild=guild, guilds=guilds)

    def get_cog(self, name_or_guild_id: Union[str, int]) -> Optional[commands.Cog]:
        """
        Get a cog from the bot.

        Overridden for custom cogs
        """
        if isinstance(name_or_guild_id, int):
            return self.custom_cogs.get(name_or_guild_id, None)

        return super().get_cog(name_or_guild_id)

    async def remove_cog(
        self,
        name_or_guild_id: Union[str, int],
        /,
        *,
        guild: Optional[discord.abc.Snowflake] = discord.utils.MISSING,
        guilds: typing.Sequence[discord.abc.Snowflake] = discord.utils.MISSING,
    ) -> Optional[commands.Cog]:
        """
        Remove a cog from the bot.

        This method is overridden to add support for custom cogs,
        which only work in specified guilds.
        """
        if isinstance(name_or_guild_id, int):
            guild_id = name_or_guild_id
            cog = self.custom_cogs.pop(guild_id, None)
            if cog == None:
                return

            if cog.__cog_app_commands_group__:
                self.__tree.remove_command(
                    cog.__cog_app_commands_group__.name, guild=discord.Object(guild_id)
                )

            await cog._eject(self, guild_ids=[])

            return cog

        return await super().remove_cog(name_or_guild_id, guild=guild, guilds=guilds)

    async def send_ext_for_review(
        self, guild_id: int, url: Union[str, Dict[str, str]], name: Optional[str]
    ):
        db = self.get_db("CustomCogs", cog=False)
        data = await db.find_one({"_id": guild_id})
        if data:
            await self.delete_review(guild_id)

        await db.insert_one(
            {
                "_id": guild_id,
                "status": ReviewStatus.pending.value,
                "url": url,
                "name": name,
            }
        )

        g = self.get_guild(guild_id)
        n = f"**{g.name}** (`{guild_id}`)" if g else f"**`{guild_id}`**"
        total = await db.count_documents({"status": ReviewStatus.pending.value})
        await self.send_to_webhook(
            f"Guild {n} sent an extension for review. "
            f"There are now {total} extensions to be approved."
        )

    async def delete_review(self, guild_id: int):
        db = self.get_db("CustomCogs", cog=False)
        await db.delete_one({"_id": guild_id})

    async def download_extension(self, url: Union[str, Dict[str, str]], name: str):
        """
        Download a cog from a git repository or the URL.

        There is few to no error handling here because we are assuming
        that the code has been approved and follows the rules.
        """
        with tempfile.TemporaryDirectory(prefix="sb-") as dirname:
            is_message = isinstance(url, dict)
            is_repo = False
            if not is_message:
                is_repo = True
                try:
                    await self.loop.run_in_executor(
                        self.__git_exec,
                        partial(
                            pygit2.clone_repository,
                            url,
                            os.path.join(dirname, "repo"),
                        ),
                    )
                except Exception:
                    is_repo = False

            if is_repo:
                dir = os.path.join(dirname, "repo")
                name = os.path.splitext(name)[0] if name else "main"
                code = open(os.path.join(dir, f"{name}.py")).read()
                reqf = os.path.join(dir, "requirements.txt")
                if os.path.exists(reqf):
                    requirements = ["-r", reqf]
                else:
                    requirements = find_requirements(code)
            else:
                if is_message:
                    chn = self.get_channel(url["channel_id"])  # type: ignore
                    msg = await chn.fetch_message(url["message_id"])  # type: ignore
                    url = msg.attachments[0].url

                async with self.session.get(url) as req:
                    code = (await req.content.read()).decode()
                    requirements = find_requirements(code)

            return code, requirements

    async def get_ext_status(self, guild_id: int) -> Optional[ReviewStatus]:
        """
        Get the status of a custom extension.
        """
        db = self.get_db("CustomCogs", cog=False)
        data = await db.find_one({"_id": guild_id})
        if not data:
            return

        return ReviewStatus(data["status"])

    async def set_ext_status(
        self, guild_id: int, status: ReviewStatus
    ) -> Optional[dict]:
        """
        Set the status of a custom extension.
        """
        db = self.get_db("CustomCogs", cog=False)
        data = await db.find_one({"_id": guild_id})
        if not data:
            return

        try:
            await db.update_one(
                {"_id": guild_id},
                {
                    "$set": {
                        "status": status.value,
                    }
                },
            )
        except Exception:
            return

        return await db.find_one({"_id": guild_id})

    async def approve_review(self, guild_id: int):
        if EXT_NAME.format(guild_id=guild_id) in self.extensions:
            await self.unload_extension(guild_id)

        data = await self.set_ext_status(guild_id, ReviewStatus.setting)
        if not data:
            return

        code, requirements = await self.download_extension(data["url"], data["name"])
        try:
            await self.setup_requirements(requirements)
            await upload_code_to_db(self.mongodb, guild_id, code)
        except Exception:
            await self.set_ext_status(guild_id, ReviewStatus.errored)
            raise

        await self.load_extension(guild_id)
        await self.set_ext_status(guild_id, ReviewStatus.ok)

    async def setup_requirements(self, requirements: list[str]):
        if not requirements:
            return

        v = sys.version_info
        ver = f"{v.major}.{v.minor}"

        proc = await asyncio.create_subprocess_shell(
            f"./tools/setup-requirements.sh {ver} {' '.join(requirements)}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        o, _ = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"Exit code {proc.returncode} trying to setup requirements:\n{o.decode()}"
            )

    async def _load_from_code(self, code: str, guild_id: int):
        name, spec, mod = custom_ext_from_code(code, guild_id)
        spec.loader.exec_module(mod)  # type: ignore
        orig_setup = getattr(mod, "setup", None)

        async def _wrap_setup(bot):
            if not orig_setup:
                await self.set_ext_status(guild_id, ReviewStatus.errored)
                return

            try:
                await orig_setup(bot, guild_id)
            except Exception:
                await self.set_ext_status(guild_id, ReviewStatus.errored)
                raise

        mod.setup = _wrap_setup  # type: ignore
        await self._load_from_module_spec(spec, name)

    async def load_extension(
        self, name_or_guild_id: Union[str, int], *, package: Optional[str] = None
    ):
        if isinstance(name_or_guild_id, int):
            guild_id = name_or_guild_id
            db = self.get_db("CustomCogs", cog=False)
            data = await db.find_one({"_id": guild_id})
            if not data:
                raise commands.ExtensionNotFound(str(guild_id))

            if data["status"] not in [
                ReviewStatus.ok.value,
                ReviewStatus.setting.value,
            ]:
                if data["status"] == ReviewStatus.errored.value:
                    raise ValueError(
                        f"Extension {guild_id} has errors and cannot be loaded"
                    )

                raise ValueError(f"Extension {guild_id} hasn't been approved yet.")

            if EXT_NAME.format(guild_id=guild_id) in self.extensions:
                raise commands.ExtensionAlreadyLoaded(str(guild_id))

            code: str = await get_ext_from_db(
                self.mongodb, guild_id, True
            )  #  type: ignore

            try:
                await self._load_from_code(code, guild_id)
            except Exception:
                await self.set_ext_status(guild_id, ReviewStatus.errored)
                raise

            return

        return await super().load_extension(name_or_guild_id, package=package)

    async def reload_extension(
        self, name: Union[str, int], *, package: Optional[str] = None
    ):
        if isinstance(name, int):
            name = EXT_NAME.format(guild_id=name)

        return await super().reload_extension(name, package=package)

    async def unload_extension(self, name: Union[str, int]):
        if isinstance(name, int):
            name = EXT_NAME.format(guild_id=name)

        return await super().unload_extension(name)

    async def _remove_module_references(self, name: str) -> None:
        gid = None
        for guild_id, cog in self.custom_cogs.copy().items():
            if _is_submodule(name, cog.__module__):
                # NOTE: remember, only one cog per guild
                await self.remove_cog(guild_id)
                gid = guild_id
                break

        if gid:
            for cmd in self.custom_commands.copy().values():
                if cmd.module is not None and _is_submodule(name, cmd.module):  # type: ignore
                    if isinstance(cmd, commands.GroupMixin):
                        cmd.recursively_remove_all_commands()

                    self.remove_command(cmd.name, gid)  # type: ignore

        return await super()._remove_module_references(name)

    # ===== Markov =====

    async def get_markov_chain(self, guild_id: int) -> Optional[MarkovChain]:
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
            await self.save_markov_chain(guild_id)  # type: ignore

        if tasks:
            await asyncio.gather(*tasks)

        self.__markov_loop_running = False

    # ===== Cleanup tasks =====

    async def close(self):
        self._closing = True
        print(end="\r")
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
                nonlocal lng
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
            t = self.markov_cache_loop.get_task()
            if self.__markov_loop_running and t:
                logger.debug("Waiting for the Markov cache loop to finish...")
                await t

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
