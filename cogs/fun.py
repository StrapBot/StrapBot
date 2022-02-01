"""thanks dankmemer for some of the commands :)"""

from enum import Enum
from random import randint, choice, shuffle
import discord
from discord.ext import commands
import box
import json
import string
import typing
import asyncio
import os
from io import BytesIO


class RPS(Enum):
    rock = "\N{MOYAI}"
    paper = "\N{PAGE FACING UP}"
    scissors = "\N{BLACK SCISSORS}"


class RPSParser:
    def __init__(self, argument):
        argument = argument.lower()
        if argument == "rock":
            self.choice = RPS.rock
        elif argument == "paper":
            self.choice = RPS.paper
        elif argument == "scissors":
            self.choice = RPS.scissors
        else:
            self.choice = None


class Fun(commands.Cog):
    """Some Fun commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["inspiro"])
    async def inspirobot(self, ctx, amount: int = 1):
        """Send an InspiroBot quote.

        NOTE: The quotes are automatically generated by an AI,
              so those might not always be family-friendly."""
        if amount <= 0 or amount > 5:
            return await ctx.send("Nope.")
        if amount == 1:
            msg = ctx.lang["messages"]["single"]
        else:
            msg = ctx.lang["messages"]["multi"]
        files = []
        for i in range(amount):
            response = await self.bot.session.get(
                "https://inspirobot.me/api?generate=true"
            )
            gen = (await response.content.read()).decode("UTF-8")
            filename = "SPOILER_" + gen.split("/")[-1]
            file = await self.bot.session.get(gen)
            file = BytesIO(await file.content.read())
            files.append(discord.File(file, filename=filename))

        shuffle(files)

        await ctx.send(
            msg,
            files=files,
        )

    @commands.command()
    async def choose(self, ctx, *, choices):
        """Choose between multiple options.
        You need to split every choice with a comma.
        Example:
        `choose Go to school, Do onlime school`
        """
        choices = choices.split(",")
        if len(choices) < 2:
            await ctx.send_help(ctx.command)
        else:
            await ctx.send(choice(choices))

    @commands.command()
    async def roll(self, ctx, number: int = 6):
        """Roll a random number.
        The result will be between 1 and `<number>`.
        `<number>` defaults to 6.
        """
        author = ctx.author
        if number > 1:
            n = randint(1, number)
            await ctx.send(
                "{author.mention} :game_die: {n} :game_die:".format(author=author, n=n)
            )
        else:
            await ctx.send("testù")

    @commands.command()
    async def flip(self, ctx):
        """Flip a coin"""
        answer = choice(["heads", "tails"])
        answer = ctx.lang[answer]
        await ctx.send(answer)

    @commands.command()
    async def rps(self, ctx, your_choice: RPSParser):
        """Play Rock,Paper,Scissors"""
        author = ctx.author
        player_choice = your_choice.choice
        if not player_choice:
            return await ctx.send(ctx.lang["invalid"])
        # TODO: translate this
        bot_choice = choice((RPS.rock, RPS.paper, RPS.scissors))
        cond = {
            (RPS.rock, RPS.paper): False,
            (RPS.rock, RPS.scissors): True,
            (RPS.paper, RPS.rock): True,
            (RPS.paper, RPS.scissors): False,
            (RPS.scissors, RPS.rock): False,
            (RPS.scissors, RPS.paper): True,
        }
        if bot_choice == player_choice:
            outcome = None  # Tie
        else:
            outcome = cond[(player_choice, bot_choice)]
        if outcome is True:
            await ctx.send(f"{bot_choice.value} {ctx.lang['win']} {author.mention}!")
        elif outcome is False:
            await ctx.send(
                f"{bot_choice.value} {ctx.langlang['lose']} {author.mention}!"
            )
        else:
            await ctx.send(f"{bot_choice.value} {ctx.lang['square']} {author.mention}!")

    @commands.command(name="8ball", aliases=["8"])
    async def _8ball(self, ctx, *, question: str):
        """Ask 8 ball a question.
        Question must end with a question mark.
        """
        if question.endswith("?") and question != "?":
            answers = (ctx.lang)["answers"]
            await ctx.send(
                f"{ctx.author.mention}, "
                + (
                    choice(answers)
                    if question != "testù?"
                    else "testù, testù, testù testù! testù testù testù"
                )
            )
        else:
            await ctx.send((ctx.lang)["question"])

    @commands.command()
    async def lmgtfy(self, ctx, *, search_terms: str):
        """Create a lmgtfy link."""
        search_terms = search_terms.replace("+", "%2B").replace(" ", "+")
        await ctx.send("<https://lmgtfy.com/?q={}>".format(search_terms))

    @commands.command()
    async def say(self, ctx, *, message):
        """Make the bot say something"""
        await ctx.send(message)

    @commands.command()
    async def reverse(self, ctx, *, text):
        """!txeT ruoY esreveR"""
        text = "".join(list(reversed(str(text))))
        await ctx.send(text)

    @commands.command()
    async def emojify(self, ctx, *, text: str):
        """Turns your text into emojis!"""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        to_send = ""
        for char in text:
            if char == " ":
                to_send += " "
            elif char.lower() in "qwertyuiopasdfghjklzxcvbnm":
                to_send += f":regional_indicator_{char.lower()}:  "
            elif char in "1234567890":
                numbers = {
                    "1": "one",
                    "2": "two",
                    "3": "three",
                    "4": "four",
                    "5": "five",
                    "6": "six",
                    "7": "seven",
                    "8": "eight",
                    "9": "nine",
                    "0": "zero",
                }
                to_send += f":{numbers[char]}: "
            else:
                return await ctx.send(ctx.lang["unsupported"])
        if len(to_send) > 2000:
            return await ctx.send(ctx.lang["toomany"])
        await ctx.send(to_send)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def roast(self, ctx, *, user: discord.Member = None):
        """
        Roast someone! If you suck at roasting them yourself.
        """
        msg = f"{user.mention},\n\n" if user is not None else ""
        roasts = ctx.lang["roasts"]
        if user != None:
            if user.id == ctx.bot.user.id:
                user = ctx.author
                msg = ctx.lang["roastyou"] + f"\n\n{user.mention}\n\n"
        else:
            msg = ""
        await ctx.send(f"{msg}{choice(roasts)}")

    @commands.command(aliases=["sc"])
    @commands.guild_only()
    async def smallcaps(self, ctx, *, message):
        """ᴄᴏɴᴠᴇʀᴛ ʏᴏᴜʀ ᴛᴇxᴛ ᴛᴏ ꜱᴍᴀʟʟ ᴄᴀᴘꜱ!!"""
        alpha = list(string.ascii_lowercase)
        converter = [
            "ᴀ",
            "ʙ",
            "ᴄ",
            "ᴅ",
            "ᴇ",
            "ꜰ",
            "ɢ",
            "ʜ",
            "ɪ",
            "ᴊ",
            "ᴋ",
            "ʟ",
            "ᴍ",
            "ɴ",
            "ᴏ",
            "ᴘ",
            "ǫ",
            "ʀ",
            "ꜱ",
            "ᴛ",
            "ᴜ",
            "ᴠ",
            "ᴡ",
            "x",
            "ʏ",
            "ᴢ",
        ]
        new = ""
        exact = message.lower()
        for letter in exact:
            if letter in alpha:
                index = alpha.index(letter)
                new += converter[index]
            else:
                new += letter
        await ctx.send(new)

    @commands.command()
    async def cringe(self, ctx, *, message):
        """mAkE ThE TeXt cRiNgY!!"""
        qpowi = randint(0, 1)
        text_list = list(message)  # convert string to list to be able to edit it
        for i in range(0, len(message)):
            if qpowi == 0:
                if i % 2 == 0:
                    text_list[i] = text_list[i].lower()
                else:
                    text_list[i] = text_list[i].upper()
            else:
                if i % 2 == 0:
                    text_list[i] = text_list[i].upper()
                else:
                    text_list[i] = text_list[i].lower()
        message = "".join(
            text_list
        )  # convert list back to string(message) to print it as a word
        await ctx.send(
            embed=discord.Embed(
                color=discord.Color.lighter_grey(), description=message
            ).set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        )
        await ctx.message.delete()

    @commands.command()
    async def meme(self, ctx):
        """Gives a random meme."""
        lang = ctx.lang.current
        if lang == "it":
            subreddit = "r/memesITA"
        else:
            subreddit = choice(["r/memes", "r/dankmemes"])
        r = await self.bot.session.get(
            f"https://www.reddit.com/{subreddit}/top.json?sort=top&t=day&limit=500"
        )
        r = await r.json()
        r = box.Box(r)
        data = choice(r.data.children).data
        img = data.url
        title = data.title
        upvotes = data.ups
        downvotes = data.downs
        em = discord.Embed(
            color=ctx.author.color,
            title=title,
            url=f"https://reddit.com{data.permalink}",
        )
        em.set_image(url=img)
        em.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        em.set_footer(text=f"👍{upvotes} | 👎 {downvotes}")
        await ctx.send(embed=em)

    @commands.command()
    async def crab(self, ctx, *, text: str):
        if len(text.split(",")) == 1 or text == "," or len(text.split(",")) > 2:
            text = "You need to split your,message with a comma"

        await ctx.message.add_reaction("⏳")

        file = await self.bot.imgen.crab(text=text)

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)
        await ctx.message.add_reaction("🦀")

    @commands.command(aliases=["yt"])
    async def youtube(
        self, ctx, author: typing.Optional[discord.Member] = None, *, text: str
    ):
        if author == None:
            author = ctx.author

        await ctx.message.add_reaction("⏳")

        file = await self.bot.imgen.youtube(
            text=text, avatars=[f"{author.avatar_url}"], usernames=[author.name]
        )

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)

    @commands.command(aliases=["wdt"])
    async def whodidthis(self, ctx, author: discord.Member = None):
        if author == None:
            author = ctx.author

        await ctx.message.add_reaction("⏳")

        image = f"{author.avatar_url}"
        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
            if url.endswith("png"):
                image = f"{ctx.message.attachments[0].url}"

        file = await self.bot.imgen.whodidthis(avatars=[image])

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)
        await ctx.message.add_reaction("😂")

    @commands.command(aliases=["wti"])
    async def whothisis(
        self, ctx, author: typing.Optional[discord.Member] = None, *, name: str = None
    ):
        if name == None and author != None:
            name = author.name
            author = ctx.author
        elif name != None:
            name = name
        else:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "name"})()
            )

        if author == None:
            author = ctx.author

        await ctx.message.add_reaction("⏳")

        image = f"{author.avatar_url}"
        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
            if url.endswith("png"):
                image = f"{ctx.message.attachments[0].url}"

        file = await self.bot.imgen.whothisis(avatars=[image], text=name)

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)
        await ctx.message.add_reaction("🤔")

    @commands.command(aliases=["cmm"])
    async def changemymind(
        self,
        ctx,
        *,
        text: str = "StrapBot is the best bot ever. (Please put some text)",
    ):
        await ctx.message.add_reaction("⏳")

        file = await self.bot.imgen.changemymind(text=text)

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)
        await ctx.message.add_reaction("🧠")
        await ctx.message.add_reaction("🔧")

    @commands.command()
    async def jail(self, ctx, author: discord.Member = None):
        if author == None:
            author = ctx.author

        await ctx.message.add_reaction("⏳")

        image = f"{author.avatar_url}"
        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
            if url.endswith("png"):
                image = f"{ctx.message.attachments[0].url}"

        file = await self.bot.imgen.jail(avatars=[image])

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)
        await ctx.message.add_reaction("👮‍♂️")

    @commands.command()
    async def award(self, ctx, author: discord.Member = None):
        if author == None:
            author = ctx.author

        await ctx.message.add_reaction("⏳")

        image = f"{author.avatar_url}"
        username = author.name
        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
            if url.endswith("png"):
                image = f"{ctx.message.attachments[0].url}"
                username = ""

        file = await self.bot.imgen.award(avatars=[image], usernames=[username])

        await ctx.message.remove_reaction("⏳", ctx.me)
        await ctx.message.add_reaction("⌛")

        await ctx.send(file=file)

        await ctx.message.remove_reaction("⌛", ctx.me)
        await ctx.message.add_reaction("🏅")

    @commands.command()
    async def fuckup(self, ctx, *, phrase: str):
        words = list(phrase)
        news = []
        for _ in range(5):
            new = ""
            for i in words:
                new += choice(words)

            news.append(new)
            await asyncio.sleep(0.5)  # avoid blocking

        await ctx.send(choice(news))

    @commands.command(usage="<text>")
    async def story(
        self, ctx, *, text: str = "text is a required argument that is missing.\n\n"
    ):
        token = os.getenv("DEEPAI_API_TOKEN")
        if not token:
            return

        resp = await self.bot.session.post(
            "https://api.deepai.org/api/text-generator",
            data={"text": text},
            headers={"api-key": token},
        )
        ret = await resp.json()
        await ctx.send(
            embed=discord.Embed(
                description=ret["output"], color=discord.Color.lighter_grey()
            ).set_author(name="Generated text", icon_url=ctx.me.avatar_url)
        )


def setup(bot):
    bot.add_cog(Fun(bot))
