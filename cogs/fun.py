from enum import Enum
from random import randint, choice
import discord
from discord.ext import commands
import box
import json
import string


def escape(text: str, *, mass_mentions: bool = False, formatting: bool = False) -> str:
    """Get text with all mass mentions or markdown escaped.
    Parameters
    ----------
    text : str
        The text to be escaped.
    mass_mentions : `bool`, optional
        Set to :code:`True` to escape mass mentions in the text.
    formatting : `bool`, optional
        Set to :code:`True` to escpae any markdown formatting in the text.
    Returns
    -------
    str
        The escaped text.
    """
    if mass_mentions:
        text = text.replace("@everyone", "@\u200beveryone")
        text = text.replace("@here", "@\u200bhere")
    if formatting:
        text = (
            text.replace("`", "\\`")
            .replace("*", "\\*")
            .replace("_", "\\_")
            .replace("~", "\\~")
        )
    return text


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
        super().__init__()
        self.bot = bot

    @commands.command()
    async def choose(self, ctx, *choices):
        """Choose between multiple options.
        To denote options which include whitespace, you should use
        double quotes.
        """
        lang = await ctx.get_lang(self)
        choices = [escape(c, mass_mentions=True) for c in choices]
        if len(choices) < 2:
            await ctx.send(_(lang["nochoose"]))
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
        lang = await ctx.get_lang(self)
        answer = choice(["heads", "tails"])
        answer = lang[answer]
        await ctx.send(answer)

    @commands.command()
    async def rps(self, ctx, your_choice: RPSParser):
        """Play Rock,Paper,Scissors"""
        lang = await ctx.get_lang(self)
        author = ctx.author
        player_choice = your_choice.choice
        if not player_choice:
            return await ctx.send(lang["invalid"])
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
            await ctx.send(f"{bot_choice.value} {lang['win']} {author.mention}!")
        elif outcome is False:
            await ctx.send(f"{bot_choice.value} {lang['lose']} {author.mention}!")
        else:
            await ctx.send(f"{bot_choice.value} {lang['square']} {author.mention}!")

    @commands.command(name="8ball", aliases=["8"])
    async def _8ball(self, ctx, *, question: str):
        """Ask 8 ball a question.
        Question must end with a question mark.
        """
        if question.endswith("?") and question != "?":
            answers = (await ctx.get_lang(self))["answers"]
            await ctx.send(
                (
                    choice(answers)
                    if question != "testù?"
                    else "testù, testù, testù testù! testù testù testù"
                )
            )
        else:
            await ctx.send((await ctx.get_lang(self))["question"])

    @commands.command()
    async def lmgtfy(self, ctx, *, search_terms: str):
        """Create a lmgtfy link."""
        search_terms = escape(
            search_terms.replace("+", "%2B").replace(" ", "+"), mass_mentions=True
        )
        await ctx.send("<https://lmgtfy.com/?q={}>".format(search_terms))

    @commands.command()
    async def say(self, ctx, *, message):
        """Make the bot say something"""
        msg = escape(message, mass_mentions=True)
        await ctx.send(msg)

    @commands.command()
    async def reverse(self, ctx, *, text):
        """!txeT ruoY esreveR"""
        text = escape("".join(list(reversed(str(text)))), mass_mentions=True)
        await ctx.send(text)

    @commands.command()
    async def emojify(self, ctx, *, text: str):
        """Turns your text into emojis!"""
        lang = await ctx.get_lang(self)
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
                return await ctx.send(lang["unsupported"])
        if len(to_send) > 2000:
            return await ctx.send(lang["toomany"])
        await ctx.send(to_send)

    @commands.command()
    @commands.guild_only()
    async def roast(self, ctx, *, user: discord.Member = None):
        """Roast someone! If you suck at roasting them yourself."""
        lang = await ctx.get_lang(self)
        msg = f"{user.mention},\n\n" if user is not None else ""
        roasts = lang["roasts"]
        if user != None:
            if user.id == ctx.bot.user.id:
                user = ctx.message.author
                msg = lang["roastyou"] + f"\n\n{user.mention}\n\n"
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
        text_list = list(message)  # convert string to list to be able to edit it
        for i in range(0, len(message)):
            if i % 2 == 0:
                text_list[i] = text_list[i].lower()
            else:
                text_list[i] = text_list[i].upper()
        message = "".join(text_list)  # convert list back to string(message) to print it as a word
        await ctx.send(embed=discord.Embed(description=message, color=discord.Color.lighter_grey()).set_author(name=f"{ctx.message.author.name}#{ctx.message.author.discriminator}", icon_url=ctx.message.author.avatar_url))
        await ctx.message.delete()


def setup(bot):
    bot.add_cog(Fun(bot))
