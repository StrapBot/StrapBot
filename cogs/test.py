import discord
from discord.ext import commands


class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="testù", pass_context=True)
    async def testu(self, ctx):
        """testù"""
        return await ctx.send(
            embed=discord.Embed(
                title="testù", description=f"testù", color=discord.Color.lighter_grey()
            )
            .set_footer(text="Made by Ergastolator#0001 and Vincy.exe#1447")
            .set_thumbnail(
                url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )

    @commands.command(pass_context=True)
    async def ping(self, ctx):
        """Shows ping."""
        return await ctx.send(
            embed=discord.Embed(
                title="Ping!",
                description=f"Total latency: {round(self.bot.latency*1000)} ms",
                color=discord.Color.lighter_grey(),
            )
            .set_footer(text="Made by Ergastolator#0001 and Vincy.exe#1447")
            .set_thumbnail(
                url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )

    @commands.command(pass_context=True)
    async def servers(self, ctx):
        """Returns the total number of servers I'm in."""
        return await ctx.send(
            embed=discord.Embed(
                title="Total servers",
                description=f"I'm in {len(self.bot.guilds)} servers!",
                color=discord.Color.lighter_grey(),
            )
            .set_footer(text="Made by Ergastolator#0001 and Vincy.exe#1447")
            .set_thumbnail(
                url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )

    @commands.command(pass_context=True)
    async def invite(self, ctx):
        """Invite me on your servers!"""
        return await ctx.send(
            embed=discord.Embed(
                title="Invite me!",
                description=f"If you want to invite me, [click here](https://strapbot.xyz/invite)!",
                color=discord.Color.lighter_grey(),
            )
            .set_footer(text="Made by Ergastolator#0001 and Vincy.exe#1447")
            .set_thumbnail(
                url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )


def setup(bot):
    bot.add_cog(Test(bot))
