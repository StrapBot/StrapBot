import os, discord, asyncio, traceback
from loadcogs import cogs
from os.path import isfile, join
from discord.ext import commands
from dotenv import load_dotenv as import_dotenv

import_dotenv()
token = os.getenv("TOKEN")

bot = commands.Bot(command_prefix="sb.")
bot.remove_command("help")

if __name__ == "__main__":
	print("Starting up!")
	print("Loading cogs...")
	for cog in cogs("cogs"):
		try:
			bot.load_extension(cog)
			print(f"Loaded {cog.replace('cogs.', '')}.")
		except Exception as e:
			print("Unable to load {cog.replace('cogs.', '')}.")
			print(traceback_format_exc())
	print("Logging in...")

@bot.event
async def on_ready():
	await bot.change_presence(
		activity=discord.Activity(
			type=discord.ActivityType.watching,
			name=f"{bot.command_prefix}help for help."
		),
		status=discord.Status.online
	)
	print('StrapBot is logged in as {0.user}!'.format(bot))

bot.run(token)
