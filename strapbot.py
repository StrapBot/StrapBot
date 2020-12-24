import os
import asyncio
import traceback
import discord
import logging
import re
from pkg_resources import parse_version
from aiohttp import ClientSession
from discord.ext import commands
from dotenv import load_dotenv as import_dotenv
from core.languages import Languages
from core.mongodb import *
from core.loops import Loops
from core.context import Context
from core.logs import StrapLog
from git import Repo

import_dotenv()

intents = discord.Intents.all()


class StrapBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=self.prefix, intents=intents)
        self._lang = None
        self._db = None
        self.token = os.getenv("TOKEN")
        self._session = None
        self._connected = asyncio.Event()
        self.wait_until_connected = self.wait_for_connected
        self._logger = None
        self._loops = Loops(self)
        self.repo = Repo(".")
        self._version = None
        self.startup()

    @property
    def logger(self) -> StrapLog:
        if self._logger is None:
            logging.setLoggerClass(StrapLog)
            self._logger = logging.getLogger("StrapBot")
            self._logger.configure(self)
        return self._logger

    def startup(self):
        print(self.version)
        self._loops.run_all()

        # load cogs
        self.exts = []
        for ext in os.listdir("cogs"):
            if ext.endswith(".py"):
                self.exts.append(ext.replace(".py", ""))

        for extension in self.exts:
            try:
                self.load_extension(f"cogs.{extension}")
            except (discord.ClientException, ModuleNotFoundError):
                if (
                    extension != ".DS_Store"
                    and extension != ".gitignore"
                    and extension != "__pycache__"
                ):
                    self.logger.error(
                        f"Failed to load extension {extension}.", exc_info=True
                    )
            except Exception:
                self.logger.error(f"Could not load cog {extension}", exc_info=True)

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    def prefix(self, bot, message):
        pxs = []
        if self.user.id == 779286377514139669:
            pxs.append("sb,")
        else:
            pxs.append("sb.")

        if message != None:
            if isinstance(message.channel, discord.DMChannel):
                pxs.append("")

        return commands.when_mentioned_or(*pxs)(bot, message)

    @property
    def version(self):
        if self._version is None:
            ver = [a for a in sorted([str(a) for a in self.repo.tags], reverse=True)[0].split(".")]
            vers = []
            for v in ver:
                vers.append(re.sub("\D", "", v))
            
            self._version = parse_version(
                ".".join(
                    vers
                )
            )
        return self._version

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            self._session = ClientSession(loop=self.loop)
        return self._session

    async def wait_for_connected(self) -> None:
        await self.wait_until_ready()
        await self._connected.wait()

    async def on_connect(self):
        async with self.session.get(
            "https://raw.githubusercontent.com/Vincysuper07/StrapBot-testuu/main/qpowieurtyturiewqop.json"
        ) as req:
            with open("testù.json", "w") as file:
                file.write((await req.content.read()).decode("UTF-8"))

        try:
            await self.db.validate_database_connection()
        except Exception:
            self.logger.critical(
                "Shutting down due to a DB connection problem.", exc_info=True
            )
            return await self.close()
        self.logger.info(
            "Connected to Discord API."
            if self.lang.default == "en"
            else "Connesso all'API di Discord."
        )
        await self.db.setup_indexes()
        self._connected.set()

    async def on_ready(self):
        await self.wait_for_connected()
        guild = self.get_guild(int(os.getenv("MAIN_GUILD_ID", 1)))
        if guild == None:
            self.logger.fatal("Invalid main guild ID.")
            return await self.close()
        if self.lang.default == "en":
            self.logger.info("StrapBot is logged in as {0.user}!".format(self))
        elif self.lang.default == "it":
            self.logger.info("StrapBot loggato come {0.user}!".format(self))
        await self.change_presence(activity=self.activity)

    async def on_command_error(self, ctx, error):
        error = getattr(error, "original", error)
        if isinstance(error, commands.CommandNotFound):
            self.logger.warning(str(error))
            return
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send(
                embed=discord.Embed(
                    title="Error", description=str(error), color=discord.Color.red()
                ).set_footer(text="You can try this on another server, though.")
            )

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(
                embed=discord.Embed(
                    title=f"Error: {ctx.prefix}{ctx.command} {ctx.command.signature}",
                    description=str(error),
                    color=discord.Color.red(),
                )
            )

        if isinstance(error, commands.NotOwner) or isinstance(
            error, commands.CheckFailure
        ):
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=(
                        "This command is either private, limited "
                        "to owners or unavailable.\nYou can't run "
                        "this command right now."
                    ),
                    color=discord.Color.red(),
                )
            )

        if ctx.command.cog.__class__.__name__.lower() == "music":
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=str(error),
                    color=discord.Color.red(),
                )
            )

        raise error

    @property
    def db(self) -> MongoDB:
        if self._db is None:
            self._db = MongoDB(self)
        return self._db

    @property
    def lang(self) -> Languages:
        if self._lang is None:
            self._lang = Languages(self)
        return self._lang

    def run(self, *args, **kwargs):
        try:
            self.loop.run_until_complete(self.start(self.token))
        except KeyboardInterrupt:
            pass
        except discord.LoginFailure:
            self.logger.critical("Invalid token")
        except Exception:
            self.logger.critical("exception", exc_info=True)
        finally:
            self.loop.run_until_complete(self.close())
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            try:
                self.loop.run_until_complete(
                    asyncio.gather(*asyncio.all_tasks(self.loop))
                )
            except asyncio.CancelledError:
                pass
            finally:
                self.loop.run_until_complete(self.session.close())
                print()
                self.logger.warning("Shutting down...")

    async def close(self, *args, **kwargs):
        self._loops.stop_all()
        if os.path.exists("testù.json"):
            os.remove("testù.json")
        await super().close()

    async def on_message(self, message):
        ctx = await self.get_context(message)
        allowed_guilds = [
            595318301127868417,
            746111972428480582,
            746111972428480582,
            698061313309540372,
        ]
        if (
            not isinstance(ctx.channel, discord.DMChannel)
            and not ctx.guild.id in allowed_guilds
        ):
            return

        messages = [
            "testù",
            "testà",
            "test+",
            "testì",
            "testè",
            "testò",
            "testàèìòù",
            "testàèìòù+",
            "yestü",
            "restū",
            "gestû",
            "ASDFGHJKLÒÀÙ",
        ]
        for index, msg in enumerate(messages):
            messages[index] = msg.lower()

        if not message.author.bot:
            if message.content.lower() in messages:
                await ctx.send(message.content)

        return await self.process_commands(message)


bot = StrapBot()

bot.run()
