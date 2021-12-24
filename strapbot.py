import os
import asyncio
import sys
import discord
import logging
import lavalink
import string
import random
import traceback
import ncs
from pymongo.errors import ServerSelectionTimeoutError
from discord_slash import error as slash_errors
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
from youtube_dl import YoutubeDL
from pkg_resources import parse_version
from aiohttp import ClientSession
from core import commands
from dotenv import load_dotenv as import_dotenv
from core.languages import Languages
from core.mongodb import *
from core.loops import Loops
from core.context import StrapContext, StrapSlashContext
from core.logs import StrapLog
from core.imgen import DankMemerImgen
from core.config import Config
from asyncspotify import Client, ClientCredentialsFlow
from discord_slash.model import (
    CogBaseCommandObject,
    CogSubcommandObject,
    BaseCommandObject,
)

import_dotenv()

intents = discord.Intents.all()
allowed_mentions = discord.AllowedMentions(
    everyone=False, users=False, roles=False, replied_user=True
)


class StrapSlashCommand(SlashCommand):
    async def _on_slash(self, to_use):  # slash commands only.
        if to_use["data"]["name"] in self.commands:

            ctx = StrapSlashContext(self.req, to_use, self._discord, self.logger)
            ctx.lang = await ctx.get_lang()
            cmd_name = to_use["data"]["name"]

            if cmd_name not in self.commands and cmd_name in self.subcommands:
                return await self.handle_subcommand(ctx, to_use)

            selected_cmd = self.commands[to_use["data"]["name"]]

            if type(selected_cmd) == dict:
                return  # this is context dict storage.

            if selected_cmd._type != 1:
                return  # If its a menu, ignore.

            if (
                selected_cmd.allowed_guild_ids
                and ctx.guild_id not in selected_cmd.allowed_guild_ids
            ):
                return

            if selected_cmd.has_subcommands and not selected_cmd.func:
                return await self.handle_subcommand(ctx, to_use)

            if "options" in to_use["data"]:
                for x in to_use["data"]["options"]:
                    if "value" not in x:
                        return await self.handle_subcommand(ctx, to_use)

            # This is to temporarily fix Issue #97, that on Android device
            # does not give option type from API.
            temporary_auto_convert = {}
            for x in selected_cmd.options:
                temporary_auto_convert[x["name"].lower()] = x["type"]

            args = (
                await self.process_options(
                    ctx.guild,
                    to_use["data"]["options"],
                    selected_cmd.connector,
                    temporary_auto_convert,
                )
                if "options" in to_use["data"]
                else {}
            )

            self._discord.dispatch("slash_command", ctx)

            await self.invoke_command(selected_cmd, ctx, args)

    def get_cog_commands(self, cog: commands.Cog):
        """
        Gets slash command from :class:`discord.ext.commands.Cog`.

        .. note::
            Since version ``1.0.9``, this gets called automatically during cog initialization.

        :param cog: Cog that has slash commands.
        :type cog: discord.ext.commands.Cog
        """
        if hasattr(cog, "_slash_registered"):  # Temporary warning
            return self.logger.warning(
                "Calling get_cog_commands is no longer required "
                "to add cog slash commands. Make sure to remove all calls to this function."
            )
        cog._slash_registered = True  # Assuming all went well
        func_list = [getattr(cog, x) for x in dir(cog)]
        res = [
            x
            for x in func_list
            if isinstance(x, (CogBaseCommandObject, CogSubcommandObject))
        ]
        res += [
            x.slash
            for x in func_list
            if isinstance(x, commands.StrapBotCommand)
            and hasattr(x, "slash")
            and isinstance(x.slash, (CogBaseCommandObject, CogSubcommandObject))
        ]
        for x in res:
            x.cog = cog
            if isinstance(x, CogBaseCommandObject):
                if x.name in self.commands:
                    raise slash_errors.DuplicateCommand(x.name)
                self.commands[x.name] = x
            else:
                if x.base in self.commands:
                    for i in x.allowed_guild_ids:
                        if i not in self.commands[x.base].allowed_guild_ids:
                            self.commands[x.base].allowed_guild_ids.append(i)
                    self.commands[x.base].has_subcommands = True
                else:
                    _cmd = {
                        "func": None,
                        "description": x.base_description,
                        "auto_convert": {},
                        "guild_ids": x.allowed_guild_ids.copy(),
                        "api_options": [],
                        "has_subcommands": True,
                        "connector": {},
                    }
                    self.commands[x.base] = BaseCommandObject(x.base, _cmd)
                if x.base not in self.subcommands:
                    self.subcommands[x.base] = {}
                if x.subcommand_group:
                    if x.subcommand_group not in self.subcommands[x.base]:
                        self.subcommands[x.base][x.subcommand_group] = {}
                    if x.name in self.subcommands[x.base][x.subcommand_group]:
                        raise slash_errors.DuplicateCommand(
                            f"{x.base} {x.subcommand_group} {x.name}"
                        )
                    self.subcommands[x.base][x.subcommand_group][x.name] = x
                else:
                    if x.name in self.subcommands[x.base]:
                        raise slash_errors.DuplicateCommand(f"{x.base} {x.name}")
                    self.subcommands[x.base][x.name] = x


class StrapBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=self.prefix,
            intents=intents,
            allowed_mentions=allowed_mentions,
        )
        self._spotify = None
        self._lang = None
        self._db = None
        self._ytdl = None
        self._ncs = None
        self._lavalink = None
        self.token = os.getenv("TOKEN")
        self._session = None
        self._connected = asyncio.Event()
        self.wait_until_connected = self.wait_for_connected
        self._logger = None
        self._loops = Loops(self)
        self._version = None
        self._imgen = None
        self._config = None

        # I prefer this to run when calling the bot instead of putting it in a property
        self.slash = StrapSlashCommand(
            self, sync_commands=True, sync_on_cog_reload=True
        )
        self.slashes = {}
        self.startup()

    @property
    def ncs(self) -> ncs.Client:
        if self._ncs == None:
            self._ncs = ncs.Client(
                loop=self.loop, session=self.session, close_session=False
            )

        return self._ncs

    @property
    def spotify(self):
        if self._spotify == None:

            self._spotify = Client(
                ClientCredentialsFlow(
                    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                )
            )
            self._spotify.http.loop = self.loop

        return self._spotify

    @property
    def config(self):
        if self._config == None:
            self._config = Config(self)

        return self._config

    @property
    def lavalink(self):
        if self._lavalink is None:
            self._lavalink = lavalink.Client(self.user.id)
            self._lavalink.add_node(
                os.getenv("LAVALINK_HOST"),
                int(os.getenv("LAVALINK_PORT", 2333)),
                os.getenv("LAVALINK_PASS"),
                os.getenv("LAVALINK_REGION"),
                os.getenv("LAVALINK_NODE", "StrapBot"),
                reconnect_attempts=100,
            )  # Host, Port, Password, Region, Name

        return self._lavalink

    @property
    def ytdl(self):
        if self._ytdl is None:
            options = {
                "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
                "noplaylist": True,
                "nocheckcertificate": True,
                "ignoreerrors": True,
                "logtostderr": False,
                "quiet": True,
                "no_warnings": True,
                "default_search": "auto",
                "source_address": "0.0.0.0",
            }
            self._ytdl = YoutubeDL(options)
            self._ytdl.cache.remove()

        return self._ytdl

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

    def prefix(self, bot, message, first=False):
        pxs = []
        px = None
        if os.getenv("BOT_PREFIX"):
            px = os.getenv("BOT_PREFIX")
        elif self.user.id == 779286377514139669:
            px = "sb,"
        else:
            px = "sb."
        
        if first:
            return px
        
        pxs.append(px)

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
        await self.spotify.authorize()
        async with self.session.get(
            "https://raw.githubusercontent.com/Vincysuper07/StrapBot-testuu/main/qpowieurtyturiewqop.json"
        ) as req:
            with open("core/languages/testù.json", "wb") as file:
                file.write(await req.content.read())

        try:
            await self.db.validate_database_connection()
        except Exception:
            self.logger.error(
                "Couldn't connect to the MongoDB database, the bot might not work properly.",
                exc_info=True,
            )
            # return await self.close()
        self.logger.info(
            "Connected to Discord API."
            if self.lang.default == "en"
            else "Connesso all'API di Discord."
        )
        self.add_listener(self.lavalink.voice_update_handler, "on_socket_response")
        self._connected.set()

    async def on_ready(self):
        await self.wait_for_connected()
        self.slashes = self.slash.commands
        guild = self.get_guild(int(os.getenv("MAIN_GUILD_ID", 1)))

        if guild == None:
            self.logger.fatal("Invalid main guild ID.")
            return await self.close()

        if self.lang.default == "en":
            self.logger.info("StrapBot is logged in as {0.user}!".format(self))
        elif self.lang.default == "it":
            self.logger.info("StrapBot loggato come {0.user}!".format(self))

        await self.change_presence(activity=self.activity)

        self.logger.debug("Updating user configurations...")
        for guild in self.guilds:
            config = await self.config.find(guild.id)
            if not config:
                await self.config.create_base(guild.id)
                self.logger.debug(f"Created configurations for guild `{guild.name}`.")

    async def on_command_error(self, ctx, error):
        error = getattr(error, "original", error)
        if isinstance(error, commands.CommandNotFound):
            self.logger.warning(str(error))
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=discord.Embed(
                    title="Error", description=str(error), color=discord.Color.red()
                ).set_footer(text="You can try this on another server, though.")
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=discord.Embed(
                    title=f"Error: {ctx.prefix}{ctx.command} {ctx.command.signature}",
                    description=str(error),
                    color=discord.Color.red(),
                )
            )
        elif (
            isinstance(error, commands.NotOwner)
            or isinstance(error, commands.CheckFailure)
        ) and ctx.command.cog.__class__.__name__.lower() != "music":
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
        elif ctx.command.cog.__class__.__name__.lower() == "music" and not isinstance(
            error, commands.CheckFailure
        ):
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=str(error),
                    color=discord.Color.red(),
                )
            )
            raise error
        elif isinstance(error, lavalink.exceptions.NodeException):
            await ctx.defer()
            while not self.lavalink.node_manager.nodes[0]._ws.connected:
                await asyncio.sleep(1)

            await self.process_commands(ctx.message)
        elif isinstance(error, ServerSelectionTimeoutError):
            await ctx.send(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description="The bot is currently limited due to a problem with our database, so most of the commands don't work.\nSorry for the inconvenience. It will be fixed as soon as possible.",
                ).set_author(name="Bot is limited", icon_url=ctx.me.avatar_url)
            )

        else:
            if os.getenv("ERRORS_WEBHOOK_URL"):
                await self.send_error(error, ctx.prefix, str(ctx.command))

            return await super().on_command_error(ctx, error)

    async def send_error(self, error, pfix=None, command=None, func=None):
        db = self.db.Errors
        _id = self.gen_error_id()
        try:
            while await db.find_one({"_id": _id}):
                _id = self.gen_error_id()
                await asyncio.sleep(1)
        except ServerSelectionTimeoutError:
            pass

        exc_info = (error.__class__, error, error.__traceback__)
        data = "".join(traceback.format_exception(*exc_info, limit=None, chain=True))
        wh = discord.Webhook.from_url(
            os.getenv("ERRORS_WEBHOOK_URL"),
            adapter=discord.AsyncWebhookAdapter(self.session),
        )
        args = "\n - " + "\n - ".join([f"`{a}`" for a in error.args])
        mainmsg = f"An unknown error occurred"
        if func and not (pfix and command):
            pfix = "method:"
            command = func

        if pfix and command:
            mainmsg += f" running `{pfix}{command}`."
        else:
            mainmsg += "."

        mainmsg += "\n"

        if len(args) > 1000:
            args = "Too long, can't send."
        
        try:
            await db.insert_one(
                {
                    "_id": _id,
                    "traceback": data,
                    "class": error.__class__.__name__,
                    "args": list(error.args),
                    "command": (pfix or "") + (command or ""),
                }
            )
        except ServerSelectionTimeoutError:
            _id = "Couldn't store error in DB."
        await wh.send(
            mainmsg
            + f"Error ID: `{_id}`\n"
            + f"Error class: `{error.__class__.__name__}`\n"
            + f"Error args: {args}\n"
        )

    def gen_error_id(self, length: int = 10):
        syms = list(string.ascii_letters + string.digits)
        return "".join([random.choice(syms) for i in range(length)])

    async def on_error(self, event_method, *args, **kwargs):
        if isinstance(sys.exc_info()[1], commands.errors.CheckFailure):
            return

        if os.getenv("ERRORS_WEBHOOK_URL"):
            await self.send_error(sys.exc_info()[1], func=event_method)
        return await super().on_error(event_method, *args, **kwargs)

    async def on_command(self, ctx):
        data = await self.config.find(ctx.author.id)
        if not data:
            await self.config.create_base(ctx.author.id, ctx.guild.id)
            self.logger.debug(f"Created configurations for user `{ctx.author}`.")
            data = await self.config.find(ctx.author.id)

    async def on_guild_join(self, guild):
        already_been_in = True
        data = await self.config.find(guild, "guilds")
        if not data:
            already_been_in = False
            await self.config.create_base(guild.id, None, "guilds")
            self.logger.debug(f"Created configurations for guild `{guild.name}`.")
            data = await self.config.find(guild.id, "guilds")
        
        channel = guild.system_channel
        perms = channel.permissions_for(guild.me)
        while not (perms.send_messages or perms.administrator):
            channel = random.choice(guild.channels)
            perms = channel.permissions_for(guild.me)
            await asyncio.sleep(1)

        msg = f"""
Hello there, I'm StrapBot! 👋
Thank you for inviting me{" again" if already_been_in else ""}!

You can check out all my functions using `{self.prefix(self, None, True)}help` or with slash commands!
"""

        embed = discord.Embed(
            description=msg,
            color=discord.Color.lighter_grey()
        ).set_author(
            name="Thanks for inviting me to your server!",
            icon_url=guild.me.avatar_url                    
        )

        await channel.send(embed=embed)
        

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
        await self.spotify.close()
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
                (await self.config.db.find_one({"_id": "users"})).get(
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

    def do_add_slash(self, command, name=None, *, dslash=False):
        name = name or (command.name or command.func.__name__)
        self.slashes[name] = command
        if dslash:
            self.slash.commands[name] = command
        return command

    async def add_slash(self, command, name=None, guild_ids=[], *, dslash=False):
        self.do_add_slash(command, name, dslash=dslash)
        name = name or (command.name or command.func.__name__)
        description = command.description or "No description."
        guild_ids = guild_ids if isinstance(guild_ids, list) else []
        guild_ids = guild_ids or [g.id for g in bot.guilds]
        for guild_id in guild_ids:
            await manage_commands.add_slash_command(
                self.user.id, self.token, guild_id, name, description
            )

    def get_slash(self, name) -> commands.SlashCommand:
        return self.slashes.get(name, None)

    def do_remove_slash(self, name):
        del self.slashes[name]

    async def get_all_slashes(self, guild):
        return await manage_commands.get_all_commands(
            self.user.id,
            self.token,
            guild.id if isinstance(guild, discord.Guild) else guild,
        )

    async def remove_slash(self, name, guild=None):
        try:
            del self.slash.commands[name]
        except KeyError:
            pass

        try:
            self.do_remove_slash(name)
        except KeyError:
            return

        guilds = self.guilds
        if guild != None:
            guilds = [guild]

        self.logger.info(name)
        for guild in guilds:
            commands = await self.get_all_slashes(guild.id)
            cmd = None
            for c in commands:
                if c["name"] == name or cmd["id"] == str(name):
                    cmd = c
                    break

            if cmd == None:
                continue

            await manage_commands.remove_slash_command(
                self.user.id, self.token, guild.id, int(cmd["id"])
            )

    def command(self, *args, **kwargs):
        def decorator(func):
            guild_ids = kwargs.get("guild_ids", None)
            kwargs["cog"] = kwargs.get("cog", False)
            kwargs.setdefault("parent", self)
            result = commands.command(*args, **kwargs)(func)
            self.add_command(result)
            self.do_add_slash(result.slash, guild_ids=guild_ids)
            return result

        return decorator


if __name__ == "__main__":
    bot = StrapBot()

    bot.run()
