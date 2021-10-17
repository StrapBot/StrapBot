import os
import discord
from discord.ext import commands


class Config(commands.Cog):
    """Configure StrapBot!"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.lang.db

    @commands.group(invoke_without_command=True, aliases=["settings", "cfg"])
    async def config(self, ctx):
        """Configure StrapBot with your favorite settings."""
        return await ctx.send_help(ctx.command)

    @config.group(invoke_without_command=True, aliases=["u"])
    async def user(self, ctx):
        """Configure StrapBot only for you."""
        return await ctx.send_help(ctx.command)

    @config.group(invoke_without_command=True, aliases=["guild", "s", "g"])
    @commands.has_guild_permissions(manage_guild=True)
    async def server(self, ctx):
        """
        Configure StrapBot for the entire server.
        **NOTE:** You will need the "Manage Server"
        permission to run this command.
        """
        return await ctx.send_help(ctx.command)

    @user.command(name="lang", aliases=["language", "l"], usage="<language>")
    async def _lang(self, ctx, lang="default"):
        """
        Change your language.
        **NOTE:** The only valid languages
        are only `en` and `it` for now.
        """
        if lang == "default":
            lang = self.bot.lang.default
        if not os.path.exists(f"core/languages/{lang}.json"):
            return await ctx.send_help(ctx.command)

        await self.bot.lang.set_user(ctx.author.id, lang=lang)

        ctx.lang = await ctx.get_lang()
        embed = discord.Embed.from_dict(ctx.lang["embed"])
        embed.color = discord.Color.lighter_grey()

        return await ctx.send(embed=embed)

    @user.command(name="beta")
    async def _beta(self, ctx):
        """
        Configure beta commands.
        """
        ctx.lang = await ctx.get_lang()

        data = (await self.db.find_one({"_id": "users"})).get(
            str(ctx.author.id)
        ) or {}
        beta = True
        if "beta" in data:
            beta = not data["beta"]

        data["beta"] = beta
        await self.db.find_one_and_update(
            {"_id": "users"},
            {"$set": {str(ctx.author.id): data}},
            upsert=True,
        )

        embed = discord.Embed.from_dict(ctx.lang["eembed" if beta else "dembed"])
        embed.color = discord.Color.lighter_grey()

        return await ctx.send(embed=embed)

    @server.command(name="lang", aliases=["language", "l"], usage="<language>")
    @commands.has_guild_permissions(manage_guild=True)
    async def lang_(self, ctx, lang="default"):
        """
        Change the server's language.
        **NOTE:** The only valid languages
        are only `en` and `it` for now.
        """
        if lang == "default":
            lang = self.bot.lang.default
        if not os.path.exists(f"core/languages/{lang}.json"):
            return await ctx.send_help(ctx.command)

        await self.bot.lang.set_guild(ctx.guild.id, ctx.author.id, lang=lang)

        ctx.lang = await ctx.get_lang()
        embed = discord.Embed.from_dict(ctx.lang["embed"])
        embed.color = discord.Color.lighter_grey()

        return await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Config(bot))
