import discord
import random
import asyncio
from io import BytesIO
from discord.ext import commands
from core.context import StrapContext
from functools import partial
from aenum import Enum
from discord.app_commands import Range as AppRange
from discord.ext.commands import Range
from typing import Union


class RockPaperScissors(Enum):
    rps_rock = "rock"
    rps_paper = "paper"
    rps_scissors = "scissors"

    @classmethod
    def _missing_(cls, name):
        for member in cls:
            if (
                member.name.lower() == name.lower()
                or member.name[:1].lower() == name[:1].lower()
            ):
                return member


# NOTE: I'm running some things that *could* block the loop
#       inside an executor to avoid them to block the loop.
#       For example, without doing this, if someone gives a
#       really long max argument in roll, or gives a lot of
#       options in choice, the bot could block to that task
#       and then go offline. It looks like they don't block
#       though, but I prefer keeping them like that because
#       I'm more sure it won't be blocked like this.


class Fun(commands.Cog):
    """Fun and random useless commands that almost nobody uses anymore."""

    emoji = "\N{face with tears of joy}"

    def __init__(self, bot):
        from strapbot import StrapBot

        self.bot: StrapBot = bot

    @commands.hybrid_command()
    async def inspirobot(self, ctx: StrapContext):
        """Send an InspiroBot quote."""
        await ctx.defer()
        url = ""
        img: BytesIO
        async with self.bot.session.get(
            "https://inspirobot.me/api?generate=true"
        ) as resp:
            url = (await resp.content.read()).decode()

        async with self.bot.session.get(url) as resp:
            img = BytesIO(await resp.content.read())

        await ctx.send(
            file=discord.File(img, filename="quote.jpg"),
            embed=discord.Embed(
                url=url, color=discord.Color.lighter_grey(), description="sent"
            )
            .set_image(url="attachment://quote.jpg")
            .set_author(
                name="InspiroBot", icon_url=ctx.me.avatar, url="https://inspirobot.me"
            ),
            url=url,
        )

    @commands.hybrid_command(name="8ball")
    async def eightball(self, ctx: StrapContext, *, question: str):
        """
        Ask the Magic 8 Ball a question.
        The question must end with a question mark.
        """
        answers = {
            "yes": [
                "It is certain.",
                "It is decidedly so.",
                "Without a doubt.",
                "Yes definitely.",
                "You may rely on it.",
                "As I see it, yes.",
                "Most likely.",
                "Outlook good.",
                "Yes.",
                "Signs point to yes.",
            ],
            "idk": [
                "Reply hazy, try again.",
                "Ask again later.",
                "Better not tell you now.",
                "Cannot predict now.",
                "Concentrate and ask again.",
            ],
            "no": [
                "Don't count on it.",
                "My reply is no.",
                "My sources say no.",
                "Outlook not so good.",
                "Very doubtful.",
            ],
        }
        if not question.endswith("?"):
            type_ = "idk"
        else:
            type_ = random.choice(list(answers.keys()))
        # I'm sorry, Python didn't let me put emoji names
        emojis = {"yes": "🟢", "idk": "⚫", "no": "🔴"}
        answer = random.choice(answers[type_])
        if question.strip() == "?":
            if random.randint(0, 3) == 1:
                return await ctx.send_help(ctx.command)

            type_ = random.choice(["yes", "no"])
            answer = answers[type_][2]
        await ctx.send(f"{emojis[type_]}🎱: {answer}")

    @commands.hybrid_command()
    async def roll(self, ctx: StrapContext, max: Range[int, 1, None] = 6):
        """Roll a random number. `max` must be higher than or equal to 1."""
        if max < 1:
            return await ctx.send_help(ctx.command)

        num = await self.bot.loop.run_in_executor(None, partial(random.randint, 0, max))
        msg = ctx.format_message("result", {"num": num})
        file = None
        if len(msg) > 2000:
            file = discord.File(BytesIO(str(num).encode()), filename="number.txt")
            msg = "file"

        return await ctx.send(msg, file=file)

    @commands.hybrid_command(aliases=["rockpaperscissors"])
    async def rps(self, ctx: StrapContext, choice: RockPaperScissors):
        # NOTE: first letter is the person, the second one is the bot.
        #       True is used when the user wins, and False is used when
        #       the user loses. If there's a tie, None is used instead.

        # TODO: generate this dict automatically
        uchoice: str = choice.value.lower()  # type: ignore
        bchoice: str = random.choice(["rock", "paper", "scissors"])
        fbchoice = ctx.format_message(bchoice)
        fuchoice = ctx.format_message(uchoice)
        combos = {
            # rock
            "rr": None,
            "rp": False,
            "rs": True,
            # paper
            "pr": True,
            "pp": None,
            "ps": False,
            # scissors
            "sr": False,
            "sp": True,
            "ss": None,
        }
        result = combos[uchoice[:1] + bchoice[:1]]
        msg = "tie"
        if result != None:
            msg = "win" if result else "lose"

        await ctx.send(msg, user_choice=fuchoice, bot_choice=fbchoice)

    @commands.hybrid_command(usage="<choice1>,<choice2>,[choice3],[...]")
    async def choose(self, ctx: StrapContext, *, choices):
        """Choose between multiple options, split by comma."""
        choices = [c.strip() for c in choices.split(",") if c.strip()]
        if len(choices) < 2:
            return await ctx.send_help(ctx.command)

        choice = await self.bot.loop.run_in_executor(
            None, partial(random.choice, choices)
        )

        file = None
        if len(choice) > 2000:
            file = discord.File(BytesIO(choice.encode()), filename=f"choice.txt")
            choice = "file"

        await ctx.send(choice, file=file)

    @staticmethod
    async def cringify(text: str):

        ret = ""
        cnt = 0
        num = random.choice([0, 1])
        for l in list(text):
            cnt += 1
            if random.randint(0, 10) == 3:
                cnt -= random.choice(([1] * 4) + ([2] * 2) + [3])

            attr = ("low" if cnt % 2 == num else "upp") + "er"

            ret += getattr(l, attr, str)()
            await asyncio.sleep(0)

        return ret

    @commands.hybrid_command()
    async def cringe(self, ctx: StrapContext, *, text: str):
        """Makes your text look cringy."""
        ret = await self.cringify(text)
        file = None
        if len(ret) > 2000:
            file = discord.File(
                BytesIO(ret.encode()), filename=f"{await self.cringify('message')}.txt"
            )
            ret = await self.cringify(ctx.format_message("file"))

        await ctx.send(ret, file=file)

    @commands.hybrid_command()
    async def reverse(self, ctx: StrapContext, *, text: str):
        """Reverse your text."""
        reverse = lambda text: "".join(list(reversed(list(text))))
        ret = reverse(text)
        file = None
        if len(ret) > 2000:
            file = discord.File(BytesIO(ret.encode()), filename="egassem.txt")
            ret = reverse(ctx.format_message("file"))

        await ctx.send(ret, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
