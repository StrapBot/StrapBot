import os
from os.path import isfile, join
import discord
import asyncio
import traceback
from aiohttp import ClientSession
from discord.ext import commands
from dotenv import load_dotenv as import_dotenv
from core.languages import default_language
from core.mongodb import *

import_dotenv()

class StrapBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="sb.")
        self.remove_command("help")
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
                self.load_extension(f'cogs.{extension}')
            except (discord.ClientException, ModuleNotFoundError):
                if extension == ".DS_Store":
                    pass
                elif extension == ".gitignore":
                    pass
                else:
                    print(f"Failed to load extension {extension}.")

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

    @property
    def db(self) -> ApiClient:
        if self._db is None:
            self._db = MongoDBClient(self)
        return self._db

    def run(self, *args, **kwargs):
        try:
            self.loop.run_until_complete(self.start(self.token))
        except KeyboardInterrupt:
            pass
        except discord.LoginFailure:
            print("Invalid token")
        except Exception:
            print("Fatal exception")
            traceback.format_exc()
        finally:
            self.loop.run_until_complete(self.logout())
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            try:
                self.loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(self.loop)))
            except asyncio.CancelledError:
                pass
            finally:
                self.loop.run_until_complete(self.session.close())
                print("Shutting down...")


bot = StrapBot()

if default_language == "en":
    bot.activity = discord.Activity(type=discord.ActivityType.watching, name=f"{len(bot.guilds)} servers! | Use {bot.command_prefix}help for help.")
elif default_language == "it":
    bot.activity = discord.Activity(type=discord.ActivityType.watching, name=f"{len(bot.guilds)} server! | Usa {bot.command_prefix}help per i comandi.")

@bot.event
async def on_ready():
	await bot.wait_for_connected()
	if default_language == "en":
		print('StrapBot is logged in as {0.user}!'.format(bot))
	elif default_language == "it":
		print("StrapBot loggato come {0.user}!".format(bot))

@bot.event
async def on_guild_join(guild):
	if default_language == "en":
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} servers! | Use {bot.command_prefix}help for help."),status=discord.Status.online)
	elif default_language == "it":
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} server! | Usa {bot.command_prefix}help per i comandi."),status=discord.Status.online)


@bot.event
async def on_guild_remove(guild):
	if default_language == "en":
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} servers! | Use {bot.command_prefix}help for help."),status=discord.Status.online)
	elif default_language == "it":
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} server! | Usa {bot.command_prefix}help per i comandi."),status=discord.Status.online)

bot.run()
