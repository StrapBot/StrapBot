import discord
import os
from discord.ext import commands

class BugReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def report(self, ctx, *, bug: str=None):
        """
        Report a bug.
        Attachments are not supported for now,
        though, you can put an image link in the message.
        """
        msg = None
        if bug == None:
            msg = await ctx.send(
                embed=discord.Embed(
                    title="Bug report",
                    description=(
                        "Please send the bug you want to report, "
                        "or type \"exit\" or \"quit\" to abort."
                    ),
                    color=discord.Color.lighter_grey()
                )
            )
            try:
                message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.guild.id == ctx.guild.id and m.channel.id == ctx.channel.id, timeout=60)
            except asyncio.TimeoutError:
                return await msg.edit(embed=discord.Embed(title="Aborted.", color=discord.Color.lighter_grey()))
            else:
                if message.content == "exit" or message.content == "quit":
                    return await msg.edit(embed=discord.Embed(title="Aborted.", color=discord.Color.lighter_grey()))
                
                bug = message.content
                
        
        guild = self.bot.get_guild(int(os.getenv("MAIN_GUILD_ID")))
        channel = discord.utils.get(guild.channels, name="strapbot-bug-report")
        if channel == None:
            return

        webhook = discord.utils.get(await channel.webhooks(), name="StrapBot bug report")
        if webhook == None:
            webhook = await channel.create_webhook(name="StrapBot bug report")
        
        if msg != None:
            await msg.delete()
        
        await webhook.send(
            username=ctx.author.name,
            avatar_url=ctx.author.avatar_url,
            embed=discord.Embed(
                title=f"Bug reported by {str(ctx.author)}!",
                description=bug,
                color=discord.Color.lighter_grey()
            ).set_footer(
                text=f"Guild ID: {ctx.guild.id}"
            )
        )
    
        await ctx.send(
            embed=discord.Embed(
                title="Reported!",
                description="Your bug has been reported!",
                color=discord.Color.lighter_grey()
            )
        )



def setup(bot):
    bot.add_cog(BugReport(bot))