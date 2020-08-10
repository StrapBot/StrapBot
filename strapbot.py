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
	for cog in cogs():
		try:
			bot.load_extension(cog)
			print(f"Loaded {cog.replace('cogs.', '')}.")
		except discord.ext.commands.errors.ExtensionNotFound:
			pass
		#TODO: Add a cog identification.
		except discord.ext.commands.errors.NoEntryPointError:
			print(f"Could not load {cog.replace('cogs.', '')}, are you sure you added the setup() function?")
		except Exception as e:
			print(f"Could not load {cog.replace('cogs.', '')}.")
			print(traceback.format_exc())
	print("Logging in...")

@bot.event
async def on_guild_leave(guild):
await bot.change_presence(
		activity=discord.Activity(
			type=discord.ActivityType.watching,
			name=f"In {len(bot.guilds)} servers! Use {bot.command_prefix}help for help."
		),
		status=discord.Status.online
	)

@bot.event
async def on_ready():
	await bot.change_presence(
		activity=discord.Activity(
			type=discord.ActivityType.watching,
			name=f"In {len(bot.guilds)} servers! Use {bot.command_prefix}help for help."
		),
		status=discord.Status.online
	)
	print('StrapBot is logged in as {0.user}!'.format(bot))

bot.run(token)
