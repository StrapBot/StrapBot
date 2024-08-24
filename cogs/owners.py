import re
import traceback
import discord
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from textwrap import indent
from core.utils import get_logger, ReviewStatus
from discord.ext import commands
from core.context import StrapContext
from typing import Literal, Optional
from datetime import datetime
from strapbot import StrapBot
from core.views import ExtensionReviewsView

logger = get_logger(__name__)


class Owners(commands.Cog):
    emoji = "\N{octagonal sign}"

    def __init__(self, bot: StrapBot):
        self.bot = bot
        self.cust_db = self.bot.get_db("CustomCogs", cog=False)

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.hybrid_command()
    async def test_error(self, ctx, message: Optional[str] = None):
        """Raise an exception"""
        raise Exception(message or "This is a test exception.")

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
        emoji = "🛑" if type_ == "error" else ("✅" if result else "☑️")
        await self.try_add_reaction(ctx.message, emoji, react)
        if not result:
            return

        file = None
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
        async with ctx.typing():
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

    async def do_sync_tree(
        self, ctx: StrapContext, guild: Optional[discord.Guild] = None
    ):
        kw = {"guild": guild} if guild else {}
        m = await ctx.send("running")
        g = f" for guild {str(guild)} ({guild.id})" if guild else ""
        logger.debug(f"Updating command tree{g}...")
        async with ctx.typing():
            await self.bot.tree.sync(**kw)
            done = ctx.format_message("done")
            await m.reply(f"{ctx.author.mention} {done}")

        logger.info(f"Command tree{g} has been synced.")

    @commands.group()
    async def sync_tree(self, ctx: StrapContext):
        await self.do_sync_tree(ctx, ctx.guild)

    @sync_tree.command(name="global")
    async def sync_global_tree(self, ctx: StrapContext):
        await self.do_sync_tree(ctx)

    @sync_tree.command(name="main")
    async def sync_main_tree(self, ctx: StrapContext):
        if not self.bot.main_guild:
            return

        await self.do_sync_tree(ctx, self.bot.main_guild)

    @commands.command()
    async def update(self, ctx: StrapContext, *args):
        args = [a.lower() for a in list(args)]
        async with ctx.typing():
            if not await self.bot.check_for_updates():
                await ctx.send("Already up to date.")
                return

            msg = None
            dbg = (
                "dbg" in args
                or "debug" in args
                or "d" in args
                or "v" in args
                or "verbose" in args
            )
            logs = []
            async for line in self.bot.update(yild=True, dbg=dbg):  # type: ignore
                logs.append(line)
                if not msg:
                    msg = await ctx.send(line)
                else:
                    await msg.edit(content="\n- ".join(logs[:-1]) + f"\n{logs[-1]}")

            await ctx.send(logs[-1])

    @commands.command()
    async def reviews(self, ctx: StrapContext):
        async with ctx.typing():
            revs_ = await self.cust_db.find().to_list(None)
            if not revs_:
                await ctx.send("no_reviews")
                return

            revs = []
            for r in revs_:
                if r["status"] != ReviewStatus.pending.value:
                    continue

                if isinstance(r["url"], dict):
                    d = r["url"]
                    c = self.bot.get_channel(d["channel_id"])
                    if c:
                        m = await c.fetch_message(d["message"])  # type: ignore
                        if m and m.attachments:
                            r["url"] = m.attachments[0].url

                    if isinstance(r["url"], dict):
                        r["url"] = "None"

                revs.append(r)

            if not revs:
                await ctx.send("no_reviews")
                return

            view = ExtensionReviewsView(ctx, *revs)
            await view.start(ctx)


async def setup(bot: StrapBot):
    await bot.add_cog(Owners(bot))
