import discord
from discord.ext import commands

class HelpCommand(commands.Cog):
	"""Class for the help command."""
	def __init__(self, bot):
		self.bot = bot

	@commands.command(name="help",pass_context=True)
	async def help(self, ctx):
		return await ctx.send(embed=discord.Embed(
			title="Help",
			description=f"Here is a list of commands.\n\n**{ctx.prefix}help** - Shows this help.",
			color=discord.Color.lighter_grey()
		)
		.add_field(name="Test", value=f"""
			**{ctx.prefix}testù** - testù
			**{ctx.prefix}ping** - Shows ping.
			**{ctx.prefix}servers** - Shows the total number of servers I'm in.
		""", inline=True)
		.add_field(name="Music (broken; don't use as for now)", value=f"""
			**{ctx.prefix}join** - Joins a voice channel.
			**{ctx.prefix}leave** - Clears the queue and leaves the voice channel.
			**{ctx.prefix}loop** - Loops the currently playing song.
			**{ctx.prefix}now** - Displays the currently playing song.
			**{ctx.prefix}pause** - Pauses the currently playing song.
			**{ctx.prefix}play** - Plays a song.
			**{ctx.prefix}queue** - Shows the player's queue.
			**{ctx.prefix}remove** - Removes a song from the queue at a given index.
			**{ctx.prefix}resume** - Resumes a currently paused song.
			**{ctx.prefix}shuffle** - Shuffles the queue.
			**{ctx.prefix}skip** - Skips a song.
			**{ctx.prefix}stop** - Stops playing song and clears the queue.
			**{ctx.prefix}summon** - Summons the bot to a voice channel.
		""", inline=True)
		.add_field(name="Fun", value=f"""
			**{ctx.prefix}choose** - Choose between multiple options.
			**{ctx.prefix}roll** - Roll a random number.
			**{ctx.prefix}flip** - Flip a coin.
			**{ctx.prefix}rps** - Play Rock, Paper, Scissors.
			**{ctx.prefix}8ball** - Ask 8 ball a question.
			**{ctx.prefix}lmgtfy** - Create a lmgtfy link.
			**{ctx.prefix}say** - Make the bot say something.
			**{ctx.prefix}reverse** - !txet ruoy esreveR
			**{ctx.prefix}emojify** - Turns your text into emojis!
			**{ctx.prefix}roast** - Roast someone! If you suck at roasting them yourself.
			**{ctx.prefix}smallcaps** - ᴄᴏɴᴠᴇʀᴛ ʏᴏᴜʀ ᴛᴇxᴛ ᴛᴏ ꜱᴍᴀʟʟ ᴄᴀᴘꜱ!!
			**{ctx.prefix}cringe** - mAkE ThE TeXt cRiNgY!!
		""", inline=False)
		.set_footer(text="Made by Ergastolator#0001")
		.set_author(name="StrapBot",icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64")
		.set_thumbnail(url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"))

def setup(bot):
        bot.add_cog(HelpCommand(bot))
