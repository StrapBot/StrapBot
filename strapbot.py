import os
from os.path import isfile, join
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv as import_dotenv

import_dotenv()
token = os.getenv("TOKEN")

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
	print('StrapBot is logged in as {0.user}!'.format(bot))

@bot.event
async def on_guild_join(guild):
	await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} servers! | Use {bot.command_prefix}help for help."),status=discord.Status.online)

@bot.event
async def on_guild_leave(guild):
	await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=f"{len(bot.guilds)} servers! | Use {bot.command_prefix}help for help."),status=discord.Status.online)

bot.run(token)
