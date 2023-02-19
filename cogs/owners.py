import re
import traceback
import discord
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from textwrap import indent
from core.utils import get_logger
from discord.ext import commands
from core.context import StrapContext
from typing import Literal

logger = get_logger(__name__)


class Owners(commands.Cog):
    emoji = "\N{octagonal sign}"

    def __init__(self, bot):
        from strapbot import StrapBot

        self.bot: StrapBot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.hybrid_command()
    async def raisa(self, ctx):
        """Raise an exception"""
        raise Exception(ctx.author.name + " è mona")

    @staticmethod
    async def try_add_reaction(message, reaction, do: bool = True):
        if not do:
            return True  # pretend the reaction was added

        try:
            await message.add_reaction(reaction)
        except discord.HTTPException:
            return False
        return True

    @staticmethod
    async def try_remove_reaction(message, reaction, do: bool = True):
        if not do:
            return True  # pretend the reaction was removed
        try:
            await message.remove_reaction(reaction, message.guild.me)
        except discord.HTTPException:
            return False
        return True

    async def send_eval_result(
        self, ctx: StrapContext, type_: str, result: str, react: bool = True
    ):
        emoji = "🥴" if type_ == "error" else "😀"
        await self.try_add_reaction(ctx.message, emoji, react)

        file = None
        if not result:
            await self.try_add_reaction(ctx.message, "🐟", react)
            return
        newresult = f"```py\n{result}\n```"
        if len(newresult) > 2000:
            file = discord.File(BytesIO(result.encode()), filename="output.py")
            result = "file"
            await self.try_add_reaction(ctx.message, "⏳", react)
        elif result == None:
            return
        else:
            result = newresult

        await ctx.send(result, file=file)
        await self.try_remove_reaction(ctx.message, "⏳", react)

    @commands.command(name="eval")
    async def eval_(self, ctx: StrapContext, *, body: str):
        """Evaluate a Python code."""
        body = body.strip()
        type_ = "done"
        p = re.compile(r"```.*").match(body)
        if p and body.endswith("```"):
            body = "```".join(body.replace(p.group(0), "", 1).split("```")[:-1])

        logger.warning(f"Running eval body:\n{body}")

        body = f"async def func():\n{indent(body, '    ')}"
        vars = {
            "bot": self.bot,
            "ctx": ctx,
            "message": ctx.message,
            "member": ctx.author,
            "author": ctx.author,
            "user": await self.bot.fetch_user(ctx.author.id),
            "channel": ctx.channel,
            "guild": ctx.guild,
            "discord": discord,
            "comamnds": commands,
        }
        vars.update(globals())
        result = None

        try:
            exec(body, vars)
        except Exception:
            type_ = "error"
            result = traceback.format_exc()

        stdout = StringIO()
        with redirect_stdout(stdout):
            try:
                result = await vars["func"]()
            except Exception:
                if type_ != "error":
                    type_ = "error"
                    result = traceback.format_exc()

        result = result if result != None else ""
        result = f"{stdout.getvalue()}\n{result}".strip()

        await self.send_eval_result(ctx, type_, result)

    async def load_ext(
        self, ctx: StrapContext, action_: Literal["reload", "unload", "load"], ext: str
    ):
        action = action_.lower()
        extension = "cogs."

        if ext.startswith(".."):
            ext = ext.replace("..", "", 1)
            extension = ""

        extension += ext

        logger.debug(f"Trying to {action} {extension}...")
        if action not in ["reload", "unload", "load"]:
            raise ValueError('action must be one of "load", "unload" and "reload".')

        try:
            await getattr(self.bot, f"{action}_extension")(extension)
        except Exception:
            logger.error(f"Couldn't {action} {extension}")
            await ctx.send("error", extension=extension)
            raise

        logger.info(f"Successfully {action}ed {extension}")
        await ctx.send("done", extension=extension)

    @commands.command()
    async def load(self, ctx: StrapContext, ext: str):
        await self.load_ext(ctx, "load", ext)

    @commands.command()
    async def unload(self, ctx: StrapContext, ext: str):
        await self.load_ext(ctx, "unload", ext)

    @commands.command()
    async def reload(self, ctx: StrapContext, ext: str):
        await self.load_ext(ctx, "reload", ext)

    @commands.command()
    async def error(self, ctx: StrapContext, code: str):
        db = self.bot.get_db("Errors", cog=False)
        data = await db.find_one({"_id": code})  # type: ignore
        if data == None:
            await ctx.send("not_found")
            return

        await self.send_eval_result(ctx, "error", data["traceback"], False)


async def setup(bot):
    await bot.add_cog(Owners(bot))
