import json
import discord
import inspect
import traceback
from io import StringIO
from textwrap import indent
from contextlib import redirect_stdout
from discord.ext import commands

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
        
    @commands.command(hidden=True, name="eval", aliases=["exec"])
    async def eval_(self, ctx, *, body: str):
        """Avvia un codice Python."""

        print(f"Running eval command:\n{body}")

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

        body = cleanup_code(body)
        stdout = StringIO()

        to_compile = f'async def func():\n{indent(body, "  ")}'

        def paginate(text: str):
            """Simple generator that paginates text."""
            last = 0
            pages = []
            appd_index = curr = None
            for curr in range(0, len(text)):
                if curr % 1980 == 0:
                    pages.append(text[last:curr])
                    last = curr
                    appd_index = curr
            if appd_index != len(text) - 1:
                pages.append(text[last:curr])
            return list(filter(lambda a: a != "", pages))

        try:
            exec(to_compile, env)
        except Exception as exc:
            await ctx.send(f"```py\n{exc.__class__.__name__}: {exc}\n```")
            return await ctx.message.add_reaction("⁉️")

        run_eval = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await run_eval()
        except Exception:
            value = stdout.getvalue()
            paginated_text = paginate(f"{value}{traceback.format_exc()}")
            for page in paginated_text:
                if page == paginated_text[-1]:
                    await ctx.send(f"```py\n{page}\n```")
                    break
                await ctx.send(f"```py\n{page}\n```")
            return await ctx.message.add_reaction("⁉️")

        else:
            await ctx.message.add_reaction("✅")
            value = stdout.getvalue()
            if ret is None:
                if value:
                    try:
                        await ctx.send(f"```py\n{value}\n```")
                    except Exception:
                        paginated_text = paginate(value)
                        for page in paginated_text:
                            if page == paginated_text[-1]:
                                await ctx.send(f"```py\n{page}\n```")
                                break
                            await ctx.send(f"```py\n{page}\n```")
            else:
                try:
                    await ctx.send(f"```py\n{value}{ret}\n```")
                except Exception:
                    paginated_text = paginate(f"{value}{ret}")
                    for page in paginated_text:
                        if page == paginated_text[-1]:
                            await ctx.send(f"```py\n{page}\n```")
                            break
                        await ctx.send(f"```py\n{page}\n```")


def setup(bot):
    bot.add_cog(OwnerOnly(bot))
