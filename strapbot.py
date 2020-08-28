import os
from os.path import isfile, join
import pymongo
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv as import_dotenv
from core.languages import default_language

import_dotenv()
token = os.getenv("TOKEN")

db = pymongo.MongoClient(os.getenv("MONGO_URI"))

bot = commands.Bot(command_prefix="sb.")
bot.remove_command("help")

if __name__ == "__main__":
	for extension in [f.replace(".py", "") for f in os.listdir("cogs") if isfile(join("cogs", f))]:
		try:
			bot.load_extension(f'cogs.{extension}')
		except (discord.ClientException, ModuleNotFoundError):
			if extension == ".DS_Store":
				pass
			elif extension == ".gitignore":
				pass
			else:
				print(f"Failed to load extension {extension}.")
				print(traceback_format_exc())

@bot.event
async def on_ready():
	await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} servers! | Use {bot.command_prefix}help for help."),status=discord.Status.online)
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

bot.run(token)
