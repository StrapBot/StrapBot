from enum import Enum
from random import randint,choice
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
        text = text.replace("`", "\\`").replace("*", "\\*").replace("_", "\\_").replace("~", "\\~")
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
  
    ball = [
        "As I see it, yes",
        "It is certain",
        "It is decidedly so",
        "Most likely",
        "Outlook good",
        "Signs point to yes",
        "Without a doubt",
        "Yes",
        "Yes – definitely",
        "You may rely on it",
        "Reply hazy, try again",
        "Ask again later",
        "Better not tell you now",
        "Cannot predict now",
        "Concentrate and ask again",
        "Don't count on it",
        "My reply is no",
        "My sources say no",
        "Outlook not so good",
        "Very doubtful"
    ]
    def __init__(self,bot):
        super().__init__()
        self.bot = bot
        #self.db = bot.plugin_db.get_partition(self)
        
    @commands.command()
    async def choose(self, ctx, *choices):
        """Choose between multiple options.
        To denote options which include whitespace, you should use
        double quotes.
        """
        choices = [escape(c, mass_mentions=True) for c in choices]
        if len(choices) < 2:
            await ctx.send(_("Not enough options to pick from."))
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
            await ctx.send("{author.mention} :game_die: {n} :game_die:".format(author=author, n=n))
        else:
            await ctx.send(_("{author.mention} Maybe higher than 1? ;P").format(author=author))
            
    @commands.command()
    async def flip(self,ctx):
        """Flip a coin"""
        answer = choice(["HEADS!*","TAILS!*"])
        await ctx.send(f"*Flips a coin and...{answer}")
        
    @commands.command()
    async def rps(self,ctx,your_choice:RPSParser):
        """Play Rock,Paper,Scissors"""
        author = ctx.author
        player_choice = your_choice.choice
        if not player_choice:
            return await ctx.send("This isn't a valid option. Try rock, paper, or scissors.")
        #TODO: translate this
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
            await ctx.send(f"{bot_choice.value} You win {author.mention}!")
        elif outcome is False:
            await ctx.send(f"{bot_choice.value} You lose {author.mention}!")
        else:
            await ctx.send(f"{bot_choice.value} We're square {author.mention}!")
            
    @commands.command(name="8ball",aliases=["8"])
    async def _8ball(self, ctx, *, question: str):
        """Ask 8 ball a question.
        Question must end with a question mark.
        """
        if question.endswith("?") and question != "?":
            await ctx.send((choice(self.ball) if question != "testù?" else "testù, testù, testù testù! testù testù testù"))
        else:
            await ctx.send("That doesn't look like a question.")
        
    @commands.command()
    async def lmgtfy(self, ctx, *, search_terms: str):
        """Create a lmgtfy link."""
        search_terms = escape(
            search_terms.replace("+", "%2B").replace(" ", "+"), mass_mentions=True
        )
        await ctx.send("<https://lmgtfy.com/?q={}>".format(search_terms))
        
    @commands.command()
    async def say(self,ctx,* ,message):
        """Make the bot say something"""
        for guild in self.bot.guilds:
            if guild.name == "InfinityTECH" and guild.id == 725719209228763136:
                await ctx.send("this command is blacklisted on this server due to abuse, I'm sorry.")
                break
            else:
                continue

            msg = escape(message,mass_mentions=True)
            await ctx.send(msg)
            break

    @commands.command()
    async def reverse(self, ctx, *, text):
        """!txeT ruoY esreveR"""
        text =  escape("".join(list(reversed(str(text)))),mass_mentions=True)
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
            elif char.lower() in 'qwertyuiopasdfghjklzxcvbnm':
                to_send += f":regional_indicator_{char.lower()}:  "
            elif char in '1234567890':
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
                    "0": "zero"
                }
                to_send += f":{numbers[char]}: "
            else:
                return await ctx.send("Characters must be either a letter or number. Anything else is unsupported.")
        if len(to_send) > 2000:
            return await ctx.send("Emoji is too large to fit in a message!")
        await ctx.send(to_send)
        
    @commands.command()
    @commands.guild_only()
    async def roast(self, ctx,*, user: discord.Member = None):
        '''Roast someone! If you suck at roasting them yourself.'''
   
        msg = f"Hey, {user.mention}! " if user is not None else ""
        roasts = ["I'd give you a nasty look but you've already got one.", "If you're going to be two-faced, at least make one of them pretty.", "The only way you'll ever get laid is if you crawl up a chicken's ass and wait.", "It looks like your face caught fire and someone tried to put it out with a hammer.", "I'd like to see things from your point of view, but I can't seem to get my head that far up your ass.", "Scientists say the universe is made up of neutrons, protons and electrons. They forgot to mention morons.", "Why is it acceptable for you to be an idiot but not for me to point it out?", "Just because you have one doesn't mean you need to act like one.", "Someday you'll go far... and I hope you stay there.", "Which sexual position produces the ugliest children? Ask your mother.", "No, those pants don't make you look fatter - how could they?", "Save your breath - you'll need it to blow up your date.", "If you really want to know about mistakes, you should ask your parents.", "Whatever kind of look you were going for, you missed.", "Hey, you have something on your chin... no, the 3rd one down.", "I don't know what makes you so stupid, but it really works.", "You are proof that evolution can go in reverse.", "Brains aren't everything. In your case they're nothing.", "I thought of you today. It reminded me to take the garbage out.", "You're so ugly when you look in the mirror, your reflection looks away.", "Quick - check your face! I just found your nose in my business.", "It's better to let someone think you're stupid than open your mouth and prove it.", "You're such a beautiful, intelligent, wonderful person. Oh I'm sorry, I thought we were having a lying competition.", "I'd slap you but I don't want to make your face look any better.", "You have the right to remain silent because whatever you say will probably be stupid anyway."]
        if str(user.id) == str(ctx.bot.user.id):
            return await ctx.send(f"Uh?!! Nice try! I am not going to roast myself. Instead I am going to roast you now.\n\n {ctx.author.mention} {choice(roasts)}")
        await ctx.send(f"{msg} {choice(roasts)}")

    @commands.command(aliases=['sc'])
    @commands.guild_only()
    async def smallcaps(self,ctx,*,message):
        """ᴄᴏɴᴠᴇʀᴛ ʏᴏᴜʀ ᴛᴇxᴛ ᴛᴏ ꜱᴍᴀʟʟ ᴄᴀᴘꜱ!!"""
        alpha = list(string.ascii_lowercase)     
        converter = ['ᴀ', 'ʙ', 'ᴄ', 'ᴅ', 'ᴇ', 'ꜰ', 'ɢ', 'ʜ', 'ɪ', 'ᴊ', 'ᴋ', 'ʟ', 'ᴍ', 'ɴ', 'ᴏ', 'ᴘ', 'ǫ', 'ʀ', 'ꜱ', 'ᴛ', 'ᴜ', 'ᴠ', 'ᴡ', 'x', 'ʏ', 'ᴢ']
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
    async def cringe(self,ctx,* ,message):
        """mAkE ThE TeXt cRiNgY!!"""
        text_list = list(message) #convert string to list to be able to edit it
        for i in range(0,len(message)):
            if i % 2 == 0:
                text_list[i]= text_list[i].lower()
            else:
                text_list[i]=text_list[i].upper()
        message ="".join(text_list) #convert list back to string(message) to print it as a word
        await ctx.send(message)
        await ctx.message.delete()

      
def setup(bot):
    bot.add_cog(Fun(bot))
