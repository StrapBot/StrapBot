import discord
import typing
from discord_slash import SlashContext
from core.context import StrapContext
from core import commands

# from discord_slash.cog_ext import cog_slash


# testing command in a testing cog for a testing guild
class TestingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(guild_ids=[802485584416866324])
    async def testolone(
        self,
        ctx: typing.Union[StrapContext, SlashContext],
        *,
        mona: discord.Member,
        marso=None,
    ):
        await ctx.send("seha e buon testù a tutti")
        await ctx.send(f"soprattutto a {mona.mention}")
        if ctx.author.id == 726381259332386867:
            await ctx.send(
                "in realtà soprattutto a te che sei Vincy e mi hai creato ma shhhh",
                hidden=True,
            )
        elif ctx.author.id == ctx.guild.owner.id:
            await ctx.send(
                "in realtà soprattutto a te che sei l'owner del server ma shhhh",
                hidden=True,
            )
        else:
            await ctx.send("no a te no :c", hidden=True)
        await ctx.send(marso if marso else "testùùùù")


def setup(bot):
    bot.add_cog(TestingCog(bot))
