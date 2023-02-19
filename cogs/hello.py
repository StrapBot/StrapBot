import discord
import random
import asyncio
from discord.ext import commands
from core.context import StrapContext
from core.views import PaginationView
from core.utils import get_command_lang_file, get_lang_command_file_path


class HelloCog(commands.Cog, name="Hello World, this is a test cog"):
    emoji = "\N{waving hand sign}"

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def num_to_exp(num):
        exps = list("⁰¹²³⁴⁵⁶⁷⁸⁹")
        ns = [int(n) for n in list(str(num))]
        return "".join([exps[n] for n in ns])

    @commands.hybrid_command()
    async def hi(self, ctx: StrapContext):
        """test"""
        e = lambda i: discord.Embed(title=i, description="prova")
        v = PaginationView(*[random.choice([f"prova{i}", e(i)]) for i in range(100)])
        await v.start(ctx)

    @commands.hybrid_command()
    async def seha(self, ctx: StrapContext):
        """seha"""

        await ctx.reply("seha")
        e = lambda n: discord.Embed(
            title="stupidometro", description=f"vinche è uno stupido{n}"
        )
        pgs = []
        for i in range(1, 1001):

            pgs.append(self.num_to_exp(i) if i != 1 else "")

        m = []
        for n in pgs:
            m.append(random.choice([e(n), [e(n)] * random.randint(1, 5)]))
        v = PaginationView(*m)
        await v.start(ctx, ephemeral=True)

    @commands.hybrid_group()
    async def buongiorno(self, ctx: StrapContext):
        """Buongiorno mona"""
        await ctx.send("sei mona :)")
        await ctx.send_help(ctx.command)

    @buongiorno.command()
    async def mona(self, ctx: StrapContext, n=1):
        """Dai del mona al bot"""
        n = self.num_to_exp(n) if n != 1 else ""
        await ctx.send(f"magari mona{n} sei tu")

    @commands.group()
    async def test1(self, ctx):
        await ctx.send(
            f"test1\nget_command_lang_file: `{get_command_lang_file(ctx.config.lang, ctx.command)}`\nget_lang_command_file_path: `{get_lang_command_file_path(ctx.config.lang, ctx.command)}`"
        )

    @test1.group()
    async def test2(self, ctx):
        await ctx.send(
            f"test2\nget_command_lang_file: `{get_command_lang_file(ctx.config.lang, ctx.command)}`\nget_lang_command_file_path: `{get_lang_command_file_path(ctx.config.lang, ctx.command)}`"
        )

    @test2.group()
    async def test3(self, ctx):
        await ctx.send(
            f"test3\nget_command_lang_file: `{get_command_lang_file(ctx.config.lang, ctx.command)}`\nget_lang_command_file_path: `{get_lang_command_file_path(ctx.config.lang, ctx.command)}`"
        )

    @test3.group()
    async def test4(self, ctx):
        await ctx.send(
            f"test4\nget_command_lang_file: `{get_command_lang_file(ctx.config.lang, ctx.command)}`\nget_lang_command_file_path: `{get_lang_command_file_path(ctx.config.lang, ctx.command)}`"
        )

    @test4.command()
    async def test5(self, ctx):
        await ctx.send(
            f"test5\nget_command_lang_file: `{get_command_lang_file(ctx.config.lang, ctx.command)}`\nget_lang_command_file_path: `{get_lang_command_file_path(ctx.config.lang, ctx.command)}`"
        )

    @commands.hybrid_command()
    async def aspetta(self, ctx: StrapContext):
        await ctx.send(
            "ok, aspetto un qualsiasi messaggio che qualsiasi persona può mandare"
        )
        m = await ctx.wait_for("message")

        await ctx.send(
            ("(ping rilevato @everyone)" if "@everyone" in m.content else "")
            + m.content
        )


async def setup(bot):
    await bot.add_cog(HelloCog(bot))
