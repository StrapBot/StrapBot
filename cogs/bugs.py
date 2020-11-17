import discord
from discord.ext import commands

class BugReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def report(self, ctx, *, bug: str=None):
        """Report a bug"""
        

def setup(bot):
    bot.add_cog(BugReport(bot))