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
from core.context import StrapContext
from core.logs import StrapLog
from core.imgen import DankMemerImgen

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
        self._version = None
        self._imgen = None
        self.voice_states = {}
        self.startup()

    @property
    def imgen(self) -> DankMemerImgen:
        if self._imgen is None:
            self._imgen = DankMemerImgen(self)
        return self._imgen

    @property
    def logger(self) -> StrapLog:
        if self._logger is None:
            logging.setLoggerClass(StrapLog)
            self._logger = logging.getLogger("StrapBot")
            self._logger.configure(self)
        return self._logger

    def startup(self):
        ver = str(self.version)
        if not ver.startswith("v") and not ver.startswith("pre"):
            ver = f"v{self.version}"

        self.logger.info(f"StrapBot {ver}")
        if "pre" in ver:
            self.logger.warning(
                "This is a pre-release.\nPlease consider "
                "getting the latest\nstable version to not "
                "encounter any bugs."
            )
        self._loops.run_all()

        # load cogs
        self.exts = []
        for ext in os.listdir("cogs"):
            if ext.endswith(".py"):
                self.exts.append(ext.replace(".py", ""))

        self.logger.info("Loading extensions...")
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
                self.logger.error(
                    f"Could not load extension {extension}", exc_info=True
                )

    async def get_context(self, message, *, cls: commands.Context = StrapContext):
        ctx: StrapContext = await super().get_context(message, cls=cls)
        if ctx.command:
            ctx.lang = await ctx.get_lang()
        return ctx

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
            ver = (
                __import__("subprocess")
                .run("git describe --tags --abbrev=0", shell=True, capture_output=True)
                .stdout.decode("UTF-8")
                .replace("\n", "")
            )

            self._version = parse_version(ver)
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
            with open("core/languages/testù.json", "w") as file:
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

        return await super().on_command_error(ctx, error)

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
                for state in self.voice_states.values():
                    self.loop.run_until_complete(state.stop())
                self.loop.run_until_complete(self.session.close())
                print()
                self.logger.warning("Shutting down...")

    async def close(self, *args, **kwargs):
        self._loops.stop_all()
        if os.path.exists("core/languages/testù.json"):
            os.remove("core/languages/testù.json")

        return await super().close()

    async def on_message(self, message):
        ctx = await self.get_context(message)

        if self.user.id == 740140581174378527:
            if message.channel.id == 792398761866952744:  # guild-announcements
                if message.author.id != self.user.id:
                    await message.publish()
                if (
                    not "<@&792399034174144512>" in message.content
                    and not message.content.endswith("-np")
                ):
                    await message.channel.send("<@&792399034174144512>")
            elif message.channel.id == 779035653714214912:  # announcements
                if message.author.id != self.user.id:
                    await message.publish()
                if (
                    not "<@&792399102381260840>" in message.content
                    and not message.content.endswith("-np")
                ):
                    await message.channel.send("<@&792399102381260840>")
            elif message.channel.id == 800809114736263189:  # commits
                await message.publish()

        allowed_guilds = [
            595318301127868417,
            802485584416866324,
            826744685094764564,
            698061313309540372,
        ]
        if (
            not isinstance(ctx.channel, discord.DMChannel)
            and not ctx.guild.id in allowed_guilds
        ):
            return await self.process_commands(message)

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
                await ctx.send(message.content, tts=message.tts)

        return await self.process_commands(message)

    async def on_raw_reaction_add(self, payload):
        if self.user.id == 740140581174378527:
            guild = bot.get_guild(payload.guild_id)
            member = discord.utils.get(guild.members, id=payload.user_id)
            if payload.message_id == 792407522005745674:
                if str(payload.emoji) == "1️⃣":
                    await member.add_roles(guild.get_role(792399102381260840))
                elif str(payload.emoji) == "2️⃣":
                    await member.add_roles(guild.get_role(792399034174144512))

    async def on_raw_reaction_remove(self, payload):
        if self.user.id == 740140581174378527:
            guild = bot.get_guild(payload.guild_id)
            member = discord.utils.get(guild.members, id=payload.user_id)
            if payload.message_id == 792407522005745674:
                if str(payload.emoji) == "1️⃣":
                    await member.remove_roles(guild.get_role(792399102381260840))
                elif str(payload.emoji) == "2️⃣":
                    await member.remove_roles(guild.get_role(792399034174144512))

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx: StrapContext = await self.get_context(message)

        if getattr(ctx.cog, "beta", False):
            beta = (
                (await self.lang.db.find_one({"_id": "users"})).get(
                    str(ctx.author.id)
                )
                or {"beta": False}
            ).get("beta", False)
            if not beta:
                return await ctx.send(
                    embed=discord.Embed(
                        title="Warning",
                        description=(
                            "You can't use this command because it's a beta command.\n"
                            f"If you really want to use it, please use `{ctx.prefix}config user beta` first."
                        ),
                        color=discord.Color.orange(),
                    )
                )

        await self.invoke(ctx)


bot = StrapBot()

bot.run()
