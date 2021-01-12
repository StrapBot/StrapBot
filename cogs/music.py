# -*- coding: utf-8 -*-


import math
import asyncio
import discord
from discord.ext import commands
from core.voice import *


class MissingPerms(commands.MissingPermissions):
    def __init__(self, missing_perms, *args):
        self.missing_perms = missing_perms

        missing = [
            perm.replace("_", " ").replace("guild", "server") for perm in missing_perms
        ]

        if len(missing) > 2:
            fmt = "{}, and {}".format(", ".join(missing[:-1]), missing[-1])
        else:
            fmt = " and ".join(missing)
        message = "You are missing {} permission(s) to run this command.".format(fmt)
        commands.CheckFailure.__init__(
            self, message, *args
        )  # I know, this is a bad way, but at least it works.


def is_one_in_vc():
    async def check(ctx):
        users = 0
        if ctx.voice_client:
            for u in ctx.voice_client.channel.members:
                if not u.bot:
                    users += 1

        if users == 1:
            return True
        if ctx.channel.permissions_for(ctx.author).manage_channels:
            return True
        elif "dj" in [r.name.lower() for r in ctx.author.roles]:
            return True
        else:
            raise MissingPerms(["a role named DJ or Manage Channels"])

    return commands.check(check)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db.get_cog_partition(self)

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "This command can't be used in DM channels."
            )

        return True

    @commands.command(name="summon", aliases=["join"])
    async def _summon(
        self, ctx: commands.Context, *, channel: discord.VoiceChannel = None
    ):
        """Summons the bot to a voice channel.
        If no channel was specified, it joins your channel.
        """
        lang = await ctx.get_lang()

        if not channel and not ctx.author.voice:
            raise VoiceError(lang["error"])

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name="leave", aliases=["disconnect"])
    @is_one_in_vc()
    async def _leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""
        lang = await ctx.get_lang()

        if not ctx.voice_state.voice:
            raise NotPlayingError(lang["error"])

        await ctx.voice_state.stop()
        del self.bot.voice_states[ctx.guild.id]
        await ctx.message.add_reaction("👋🏻")

    @commands.command(name="now", aliases=["current", "playing", "np"])
    async def _now(self, ctx: commands.Context):
        """Displays the currently playing song."""

        await ctx.send(embed=ctx.voice_state.current.create_embed(ctx, nowcmd=True))

    @commands.command(name="pause")
    @is_one_in_vc()
    async def _pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction("⏯")

    @commands.command(name="resume")
    @is_one_in_vc()
    async def _resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction("⏯")

    @commands.command(name="stop")
    @is_one_in_vc()
    async def _stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.voice_state.songs.clear()

        ctx.voice_state.voice.stop()
        await ctx.message.add_reaction("⏹")

    @commands.command(name="sotp", hidden=True)
    @is_one_in_vc()
    async def _sotp(self, ctx: commands.Context):
        """sotp"""
        ctx.voice_state.songs.clear()

        ctx.voice_state.voice.stop()
        await ctx.message.add_reaction("<:sotp:777922129492181002>")

    @commands.command(name="skip")
    async def _skip(self, ctx: commands.Context):
        """Skips to the next song."""
        lang = await ctx.get_lang()

        if not ctx.voice_state.is_playing:
            raise NotPlayingError(lang["error"])

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction("⏭")
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 1:
                await ctx.message.add_reaction("⏭")
                ctx.voice_state.skip()
            else:
                await ctx.send(
                    embed=discord.Embed(
                        title=lang.vote.voted,
                        description=lang.vote.success,
                        color=discord.Color.lighter_grey(),
                    ).add_field(name=lang.vote.current, value=f"**{total_votes}**")
                )

        else:
            raise RuntimeError(lang["vote"]["error"])

    @commands.command(name="volume")
    async def _volume(self, ctx: commands.Context, *, volume: int = None):
        """Sets the player's volume."""

        lang = await ctx.get_lang()

        if not ctx.voice_state.is_playing:
            return await ctx.send(lang["nothing"])

        if volume == None:
            return await ctx.send(
                lang["info"].format(round(ctx.voice_state.current.source.volume * 100))
            )

        if volume < 1 or volume > 100:
            raise ValueError(lang["error"])

        before = round(ctx.voice_state.current.source.volume * 100)
        ctx.voice_state.current.source.volume = volume / 100
        await self.db.find_one_and_update(
            {"_id": "volumes"}, {"$set": {str(ctx.guild.id): volume / 100}}, upsert=True
        )
        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(volume),
                color=discord.Color.lighter_grey(),
            ).add_field(name=lang.before, value=f"{before}%")
        )

    @commands.command(name="queue")
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """
        lang = await ctx.get_lang()

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(lang["error"])

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ""
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += "`{0}.` [**{1.source.title}**]({1.source.url})\n".format(
                i + 1, song
            )

        embed = discord.Embed(
            description=lang["tracks"].format(len(ctx.voice_state.songs), queue),
            color=discord.Color.lighter_grey(),
        ).set_footer(text=lang["pages"].format(page, pages))
        await ctx.send(embed=embed)

    @commands.command(name="shuffle")
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""
        lang = await ctx.get_lang()

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(lang["error"])

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction("✅")

    @commands.command(name="remove")
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""
        lang = await ctx.get_lang()

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(lang["error"])

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction("✅")

    @commands.command(name="loop")
    async def _loop(self, ctx: commands.Context):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """
        lang = await ctx.get_lang()

        if not ctx.voice_state.is_playing:
            raise NotPlayingError(lang["error"])

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction("🔂" if ctx.voice_state.loop else "⏹️")

    @commands.command(name="play", aliases=["p"])
    async def _play(self, ctx: commands.Context, *, search: str = None):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        if (
            ctx.voice_state.is_playing
            and ctx.voice_state.voice.is_paused()
            and search == None
        ):
            return await ctx.invoke(self._resume)

        if search == None:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "search"})()
            )
        lang = await ctx.get_lang()
        first = not ctx.voice_state.is_playing
        msg = lang["queued"] if not first else lang["playing"]

        volume = (await self.db.find_one({"_id": "volumes"}) or {}).get(
            str(ctx.guild.id), 0.5
        )

        if not ctx.voice_state.voice:
            await ctx.invoke(self._summon)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                raise RuntimeError(str(e)) from e
            else:
                song = Song(source, first=first)

                await ctx.voice_state.songs.put(song)
                await asyncio.sleep(0.1)
                ctx.voice_state.current.source.volume = volume
                if not first:
                    await ctx.send(embed=song.create_embed(ctx, queued=True))

    @commands.command(name="search")
    async def _search(self, ctx: commands.Context, *, search: str):
        """Searchs for a YouTube video."""
        lang = await ctx.get_lang()
        async with ctx.typing():
            try:
                source = await YTDLSource.search_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                raise RuntimeError(str(e)) from e
            else:
                if source == "sel_invalid" or source == "timeout":
                    await ctx.send(lang[source])
                elif source == "cancel":
                    await ctx.message.add_reaction("✅")
                else:
                    if not ctx.voice_state.voice:
                        await ctx.invoke(self._summon)

                    song = Song(source)
                    await ctx.voice_state.songs.put(song)
                    await ctx.send("Inserito {} nella coda.".format(str(source)))

    @_summon.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError("You are not connected to any voice channel.")

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError("Bot is already in a voice channel.")


def setup(bot):
    bot.add_cog(Music(bot))
