import json
import discord
from discord.ext import commands

class OwnerOnly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db.get_cog_partition(self)
        self.lang_db = bot.lang.db

    def cog_check(self, ctx):
        return commands.is_owner()

    @commands.group(invoke_without_command=True)
    async def get(self, ctx):
        """ok"""
        return await ctx.send_help(ctx.command)

    @commands.group(invoke_without_command=True)
    async def set(self, ctx):
        """ok"""
        return await ctx.send_help(ctx.command)

    @set.command()
    async def guild(self, ctx, guild: int=None, language: str="en"):
        """o k"""
        if language == None:
            language = self.bot.lang.default
        try:
            await self.bot.lang.set_guild(guild=guild, member=ctx.author, lang=language)
        except Exception as e:
            await ctx.send(e)
            raise
        else:
            await ctx.send(f"```json\n{json.dumps(await self.bot.lang.get_guild(guild), indent=4)}\n```")

    @get.command()
    async def guilds(self, ctx):
        """o k"""
        guilds = await self.bot.lang.get_guilds()
        await ctx.send(f"```json\n{json.dumps(guilds, indent=4)}\n```")

    @get.command()
    async def members(self, ctx):
        """oK"""
        members = await self.bot.lang.get_members()
        await ctx.send(f"```json\n{json.dumps(members, indent=4)}\n```")

    @set.command()
    async def member(self, ctx, member: int=None, language: str="en"):
        """oK"""
        if language == None:
            language = self.bot.lang.default
        try:
            await self.bot.lang.set_user(member=member, lang=language)
        except Exception as e:
            await ctx.send(e)
            raise
        else:
            await ctx.send(f"```json\n{json.dumps(await self.bot.lang.get_user(member), indent=4)}\n```")


def setup(bot): bot.add_cog(OwnerOnly(bot))
