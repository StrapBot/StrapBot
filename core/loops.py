import os
import discord
import random
import asyncio
from discord.ext import tasks
from datetime import datetime
from pytz import timezone
from discord_slash.model import BaseCommandObject


# NEVER USE THIS ENVIRONMENT VARIABLE.
# It's used by me for the private testing bot.
testing = os.getenv("SB_ENVIRONMENT") == "dev"
tz = timezone("Europe/Rome")

def midnightify(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

class Loops:
    TWITCH_URLS = {
        "vincy": "https://twitch.tv/Vincydotzsh",
        "erg": "https://twitch.tv/JxstErg1"
    }
    
    NAMES_IDS = {
        726381259332386867: "vincy",
        "vincy": 726381259332386867,
        602819090012176384: "erg",
        "erg": 602819090012176384
    }
    def __init__(self, bot):
        self.bot = bot
        self.time = 0
        self.next_birthdays = {
            "vincy": datetime(day=22, month=3, year=datetime.today().year, tzinfo=tz),
            "erg": datetime(day=27, month=11, year=datetime.today().year, tzinfo=tz)
        }
        self.check_birthday()
        ed = "Testing" if testing else "Beta"
        self.activities = {
            "en": [
                {"name": "{guilds} servers.", "type": "competing"},
                {"name": "{members} total users.", "type": "watching"},
                {"name": "new slash commands.", "type": "watching"},
                {
                    "name": "music with the music BETA with my friends.",
                    "type": "listening",
                },
                {
                    "name": "Use {prefix}help for help.",
                    "type": "streaming",
                    "twitch_url": self.TWITCH_URLS["vincy"],
                },
                {
                    "name": f"{ed} Edition! This bot might not be as stable as the stable one.",
                    "type": "streaming",
                    "twitch_url": self.TWITCH_URLS["vincy"],
                },
                {
                    "name": "Made by {ergastolator} and {vincy}.",
                    "type": "streaming",
                    "twitch_url": self.TWITCH_URLS["erg"],
                },
            ],
            "it": [
                {"name": "{guilds} server.", "type": "competing"},
                {"name": "{members} utenti totali.", "type": "watching"},
                {"name": "i nuovi comandi slash.", "type": "watching"},
                {
                    "name": "la musica con il nuovo music BETA con i miei amici.",
                    "type": "listening",
                },
                {
                    "name": "Usa {prefix}help per i comandi.",
                    "type": "streaming",
                    "twitch_url": self.TWITCH_URLS["erg"],

                },
                {
                    "name": f"Edizione {ed}! Questo bot potrebbe essere meno stabile di quello stabile.",
                    "type": "streaming",
                    "twitch_url": self.TWITCH_URLS["vincy"],
                },
                {
                    "name": "Fatto da {ergastolator} e {vincy}.",
                    "type": "streaming",
                    "twitch_url": self.TWITCH_URLS["vincy"],
                },
            ],
        }
        random.shuffle(self.activities[bot.lang.default])

    def run_all(self):
        """Run all loops"""
        for task in dir(self):
            loop = getattr(self, task, None)
            if loop != None:
                if isinstance(loop, tasks.Loop):
                    loop.start()

    def stop_all(self):
        """Stop all loops"""
        for task in dir(self):
            loop = getattr(self, task, None)
            if loop != None:
                if isinstance(loop, tasks.Loop):
                    loop.stop()

    def check_birthday(self):
        today = midnightify(datetime.now(tz))
        for user, bday in self.next_birthdays.items():
            if (bday - today).days < 0:
                self.next_birthdays[user] = self.next_birthdays[user].replace(year=bday.year + 1)

    @tasks.loop(seconds=5)
    async def keep_checking_for_birthday(self):
        self.check_birthday()
        await asyncio.sleep(0) # this might be blocking, so...

    @tasks.loop(seconds=30)
    async def presence_loop(self):
        """A loop that changes presence every 30 seconds"""
        await self.bot.wait_until_ready()

        today = midnightify(datetime.now(tz))
        bday = None
        for user, bd in self.next_birthdays.items():
            result = (bd - today).days
            if result < 15 and result >= 0:
                bday = {"user": self.NAMES_IDS[user], "day": bd, "days": result}
        

        if bday and self.bot.user.id in [903372493316821104, 779286377514139669, 740140581174378527]:
            u = ergastolator = discord.utils.get(
                self.bot.get_all_members(), id=bday["user"]
            )
            s = "" if bday["days"] == 1 else "s"
            name = f"{bday['days']} day{s} until {u.name}'s birthday!"
            if bday["days"] == 0:
                name = f"Happy birthday, {u.name}!"
            activity = {
                "name": name,
                "type": "watching",
            }
        else:
            members = []
            for member in self.bot.get_all_members():
                if not member.bot:
                    members.append(member)

            ergastolator = discord.utils.get(
                self.bot.get_all_members(), id=602819090012176384
            )
            vincy = discord.utils.get(self.bot.get_all_members(), id=726381259332386867)

            activities = self.activities[self.bot.lang.default]
            try:
                activity = activities[self.time]
            except IndexError:
                self.time = 0
                activity = activities[self.time]

            name = activity["name"].format(
                guilds=len(self.bot.guilds),
                members=len(members),
                prefix=self.bot.command_prefix(self.bot, None)[-1],
                ergastolator=ergastolator,
                vincy=vincy,
            )

        type = getattr(discord.ActivityType, activity["type"], None)

        if type == None:
            raise AttributeError(
                f"The activity type \"{activity['type']}\" does not exist."
            )

        if type == discord.ActivityType.streaming:
            twitch_url = activity["twitch_url"] if "twitch_url" in activity else None
            if twitch_url == None:
                raise AttributeError(
                    "Streaming activity type requested, but no Twitch URL specified."
                )

            presence = discord.Streaming(name=name, url=twitch_url)
        else:
            presence = discord.Activity(name=name, type=type)

        await self.bot.change_presence(activity=presence)

        self.time += 1

    @tasks.loop()
    async def update_slashes(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(
            5
        )  # I need it to wait 5 seconds *before* running, not after.
        for name, command in list(self.bot.slash.commands.items()):
            if not name in self.bot.slashes and isinstance(command, BaseCommandObject):
                await self.bot.remove_slash(name)

        for name, command in list(self.bot.slashes.items()):
            if not name in self.bot.slash.commands and isinstance(
                command, BaseCommandObject
            ):
                await self.bot.add_slash(command, name, dslash=True)

    @tasks.loop(seconds=5)
    async def send_youtube_msg(self):
        await self.bot.wait_until_ready()
        channels = await self.bot.config.db.find_one({"_id": "youtube"}) or {}
        internal = await self.bot.config.db.find_one({"_id": "youtube_internal"}) or {}
        vids = await self.bot.config.db.find_one({"_id": "youtube_sent"}) or {}
        messages = await self.bot.config.db.find_one({"_id": "youtube_messages"}) or {}

        ls = channels.keys()
        for id_ in ls:

            if id_ == "_id":
                continue

            if internal.get(id_, None) != vids.get(id_, None):
                for chid in channels[id_]:
                    channel = self.bot.get_channel(chid)
                    if channel == None:
                        continue

                    await channel.send(
                        messages.get(f"{id_}_{channel.id}", "<link>").replace(
                            "<link>", internal[id_]
                        ),
                        allowed_mentions=discord.AllowedMentions.all(),
                    )
                    await self.bot.config.db.find_one_and_update(
                        {"_id": "youtube_sent"},
                        {"$set": {id_: internal[id_]}},
                        upsert=True,
                    )
