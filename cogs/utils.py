import discord
from discord.ext import commands
from core.help import HelpCommand

class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand(
            command_attrs={
                "name": "help",
                "aliases": ["man", "h"],
            }
        )
        bot.help_command.cog = self

        def cog_unload(self):
            self.bot.help_command = self._original_help_command

    @commands.Cog.listener()
    async def on_ready(self):
        self.ergastolator = discord.utils.get(self.bot.get_all_members(), id=602819090012176384)
        self.vincy = discord.utils.get(self.bot.get_all_members(), id=726381259332386867)
        self.footer = f"Made by {str(self.ergastolator)} and {str(self.vincy)}"


    @commands.command(name="testù", pass_context=True)
    async def testu(self, ctx):
        """testù"""
        return await ctx.send(
            embed=discord.Embed(
                title="testù", description=f"testù", color=discord.Color.lighter_grey()
            )
            .set_footer(text=self.footer)
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
            .set_footer(text=self.footer)
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
            .set_footer(text=self.footer)
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
            .set_footer(text=self.footer)
            .set_thumbnail(
                url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )


def setup(bot):
    bot.add_cog(Utilities(bot))  # TODO: translate this
