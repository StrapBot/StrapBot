import discord
from discord.ext import commands
from core.help import HelpCommand


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand(
            verify_checks=False,
            command_attrs={
                "name": "help",
                "aliases": ["man", "h"],
            },
        )
        bot.help_command.cog = self
        self.ergastolator = self.vincy = None

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.Cog.listener()
    async def on_ready(self):
        self.ergastolator = str(
            discord.utils.get(self.bot.get_all_members(), id=602819090012176384)
        )
        self.vincy = str(
            discord.utils.get(self.bot.get_all_members(), id=726381259332386867)
        )

    @commands.command(name="testù", pass_context=True)
    async def testu(self, ctx):
        """testù"""
        return await ctx.send(
            embed=discord.Embed(
                title="testù", description=f"testù", color=discord.Color.lighter_grey()
            )
            .set_footer(
                text=(await ctx.get_lang(cog=True)).ergavincy.format(
                    self.ergastolator, self.vincy
                )
            )
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
                title="Pong!",
                description=f"{ctx.lang['latency']}: {round(self.bot.latency*1000)} ms",
                color=discord.Color.lighter_grey(),
            )
            .set_footer(
                text=(await ctx.get_lang(cog=True)).ergavincy.format(
                    self.ergastolator, self.vincy
                )
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )

    @commands.command(aliases=["guilds"])
    async def servers(self, ctx):
        """Returns the total number of servers I'm in."""
        return await ctx.send(
            embed=discord.Embed(
                title=ctx.lang["title"],
                description=ctx.lang["description_"].format(len(self.bot.guilds)),
                color=discord.Color.lighter_grey(),
            )
            .set_footer(
                text=(await ctx.get_lang(cog=True)).ergavincy.format(
                    self.ergastolator, self.vincy
                )
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )

    @commands.command()
    async def invite(self, ctx):
        """Invite me on your servers!"""
        return await ctx.send(
            embed=discord.Embed(
                title=ctx.lang["title"],
                description=ctx.lang["description_"],
                color=discord.Color.lighter_grey(),
            )
            .set_footer(
                text=(await ctx.get_lang(cog=True)).ergavincy.format(
                    self.ergastolator, self.vincy
                )
            )
            .set_thumbnail(
                url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=256"
            )
            .set_author(
                name="StrapBot",
                icon_url="https://cdn.discordapp.com/avatars/740140581174378527/226deca56aaa9cbe5f27dcbf7dda732d.png?size=64",
            )
        )


def setup(bot):
    bot.add_cog(Utilities(bot))
