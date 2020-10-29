__version__ = "2.0"

import os
from os.path import isfile, join
import discord
import asyncio
import traceback
from pkg_resources import parse_version
from aiohttp import ClientSession
from discord.ext import commands
from dotenv import load_dotenv as import_dotenv
from core.languages import Languages
from core.mongodb import *
from core.context import Context

import_dotenv()

intents = discord.Intents.default()
intents.guilds = True
intents.members = True


class StrapBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="sb.", intents=intents)
        self._lang = None
        self._db = None
        self.token = os.getenv("TOKEN")
        self._session = None
        self._connected = asyncio.Event()
        self.wait_until_connected = self.wait_for_connected

        # load cogs
        self.exts = []
        for ext in os.listdir("cogs"):
            if ext.endswith(".py"):
                self.exts.append(ext.replace(".py", ""))

        for extension in self.exts:
            try:
                self.load_extension(f"cogs.{extension}")
            except (discord.ClientException, ModuleNotFoundError):
                if extension == ".DS_Store":
                    pass
                elif extension == ".gitignore":
                    pass
                else:
                    print(f"Failed to load extension {extension}.")
            except Exception:
                print(f"Could not load cog {extension}")
                raise

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    @property
    def version(self):
        return parse_version(__version__)

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            self._session = ClientSession(loop=self.loop)
        return self._session

    async def wait_for_connected(self) -> None:
        await self.wait_until_ready()
        await self._connected.wait()

    async def on_connect(self):
        try:
            await self.db.validate_database_connection()
        except Exception:
            print("Shutting down due to a DB connection problem.")
            return await self.close()
        await self.db.setup_indexes()
        self._connected.set()

    async def on_ready(self):
        await self.wait_for_connected()
        if self.lang.default == "en":
            print("StrapBot is logged in as {0.user}!".format(self))
            self.activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers! | Use {self.command_prefix}help for help.",
            )
        elif self.lang.default == "it":
            print("StrapBot loggato come {0.user}!".format(self))
            self.activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} server! | Usa {self.command_prefix}help per i comandi.",
            )
        await self.change_presence(activity=self.activity)
        try:
            await self.session.get("https://strapbot.xyz")
        except Exception:
            pass

    async def on_guild_join(guild):
        if self.lang.default == "en":
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers! | Use {self.command_prefix}help for help.",
                ),
                status=discord.Status.online,
            )
        elif self.lang.default == "it":
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} server! | Usa {self.command_prefix}help per i comandi.",
                ),
                status=discord.Status.online,
            )

    async def on_guild_remove(guild):
        if self.lang.default == "en":
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers! | Use {self.command_prefix}help for help.",
                ),
                status=discord.Status.online,
            )
        elif self.lang.default == "it":
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} server! | Usa {self.command_prefix}help per i comandi.",
                ),
                status=discord.Status.online,
            )

    async def on_command_error(self, ctx, error):
        error = getattr(error, "original", error)
        raise error

    @property
    def db(self) -> ApiClient:
        if self._db is None:
            self._db = MongoDBClient(self)
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
            print("Invalid token")
        except Exception as e:
            print("Fatal exception")
            raise
        finally:
            self.loop.run_until_complete(self.logout())
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
                print("Shutting down...")


bot = StrapBot()

bot.run()
