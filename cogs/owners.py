import json
import discord
import inspect
import random
import traceback
import string
from io import StringIO
from textwrap import indent
from contextlib import redirect_stdout
from discord.ext import commands
from core.paginator import *


def cleanup_code(content: str) -> str:
    """
    Automatically removes code blocks from the code.
    Parameters
    ----------
    content : str
        The content to be cleaned.
    Returns
    -------
    str
        The cleaned content.
    """
    # remove ```py\n```
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:-1])

    # remove `foo`
    return content.strip("` \n")


class OwnerOnly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db.get_cog_partition(self)
        self.lang_db = bot.lang.db

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.group(invoke_without_command=True)
    async def get(self, ctx):
        """ok"""
        return await ctx.send_help(ctx.command)

    @commands.command()
    async def raise_error(self, ctx):
        """raise an error"""
        gibberish = list(
            (
                string.ascii_letters
                + string.digits
                + "\\!|\"£$%&/()=?^><;:_,.-ç°§òàùé*è+'ìÀÈÌÒÙÁÉÍÓÚ\n😐🐟🧇"
            )
            * 20
        )
        random.shuffle(gibberish)
        raise Exception("".join(gibberish))

    @commands.group(invoke_without_command=True)
    async def set(self, ctx):
        """ok"""
        return await ctx.send_help(ctx.command)

    @set.command()
    async def guild(self, ctx, guild: int = None, language: str = "en"):
        """o k"""
        if language == None:
            language = self.bot.lang.default
        try:
            await self.bot.lang.set_guild(guild=guild, member=ctx.author, lang=language)
        except Exception as e:
            await ctx.send(e)
            raise
        else:
            await ctx.send(
                f"```json\n{json.dumps(await self.bot.lang.get_guild(guild), indent=4)}\n```"
            )

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
    async def member(self, ctx, member: int = None, language: str = "en"):
        """oK"""
        if language == None:
            language = self.bot.lang.default
        try:
            await self.bot.lang.set_user(member=member, lang=language)
        except Exception as e:
            await ctx.send(e)
            raise
        else:
            await ctx.send(
                f"```json\n{json.dumps(await self.bot.lang.get_user(member), indent=4)}\n```"
            )

    @commands.command()
    async def error(self, ctx, id):
        data = await self.bot.db.Errors.find_one({"_id": id})
        if data == None:
            return

        pages = []
        embed = discord.Embed(
            description=f"Viewing traceback from `{data['command']}`.",
            color=discord.Color.lighter_gray(),
        )
        paginated_text = self.paginate(data["traceback"])
        for page in paginated_text:
            pages.append(
                f"```haskell\n{page}\n```"
            )  # using haskell because it formats tracebacks better than py
        session = MessagePaginatorSession(ctx, *pages, embed=embed)
        await session.run()

    @commands.command(hidden=True, name="eval", aliases=["exec"])
    async def eval_(self, ctx, *, body: str):
        """Avvia un codice Python."""

        body = cleanup_code(body)
        self.bot.logger.warning(f"Running eval command:\n{body}")

        env = {
            "ctx": ctx,
            "bot": self.bot,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "source": inspect.getsource,
            "discord": __import__("discord"),
        }

        env.update(globals())

        stdout = StringIO()
        embed = discord.Embed(
            description="Viewing evaluation result.", color=discord.Color.lighter_grey()
        )

        to_compile = f'async def func():\n{indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as exc:
            await ctx.send(f"```py\n{exc.__class__.__name__}: {exc}\n```")
            try:
                return await ctx.message.add_reaction("⁉️")
            except (discord.errors.NotFound, discord.errors.HTTPException):
                return

        run_eval = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await run_eval()
        except Exception:
            value = stdout.getvalue()
            paginated_text = self.paginate(f"{value}{traceback.format_exc()}")
            pages = []
            try:
                await ctx.message.add_reaction("⁉️")
                await ctx.message.add_reaction("⏳")
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass
            for page in paginated_text:
                if page == paginated_text[-1]:
                    pages.append(f"```py\n{page}\n```")
            try:
                await ctx.message.remove_reaction("⏳", ctx.me)
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass
            session = MessagePaginatorSession(ctx, *pages, embed=embed)
            return await session.run()

        else:
            try:
                await ctx.message.add_reaction("✅")
                await ctx.message.add_reaction("⏳")
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass
            value = stdout.getvalue()
            pages = []
            if ret is None:
                if value:
                    paginated_text = self.paginate(value)
                    for page in paginated_text:
                        pages.append(f"```py\n{page}\n```")
                    session = MessagePaginatorSession(ctx, *pages, embed=embed)
                    await session.run()
            else:
                try:
                    await ctx.send(f"```py\n{value}{ret}\n```")
                except Exception:
                    paginated_text = self.paginate(f"{value}{ret}")
                    for page in paginated_text:
                        pages.append(f"```py\n{page}\n```")
                    session = MessagePaginatorSession(ctx, *pages, embed=embed)
                    await session.run()

            try:
                await ctx.message.remove_reaction("⏳", ctx.me)
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass

    @commands.command()
    async def reload(self, ctx, ext):
        try:
            self.bot.reload_extension(f"cogs.{ext}")
        except Exception:
            await ctx.send("testù" + ("ù" * random.randint(20, 50)))
            raise
        await ctx.send(f"Reloaded `{ext}`.")

    @staticmethod
    def paginate(text: str):
        """Simple generator that paginates text."""
        last = 0
        pages = []
        appd_index = curr = None
        for curr in range(0, len(text)):
            if curr % 1970 == 0:
                pages.append(text[last:curr])
                last = curr
                appd_index = curr
        if appd_index != len(text) - 1:
            pages.append(text[last:curr])
        return list(filter(lambda a: a != "", pages))


def setup(bot):
    bot.add_cog(OwnerOnly(bot))
