# -*- coding: utf-8 -*-

import asyncio
import discord
import typing
from discord.ext import commands
from core.context import StrapContext
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

    def cog_check(self, ctx: StrapContext):
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "This command can't be used in DM channels."
            )

        return True

    @commands.command(name="summon", aliases=["join"])
    async def _summon(
        self,
        ctx: StrapContext,
        *,
        channel: typing.Union[discord.VoiceChannel, discord.StageChannel] = None,
    ):
        """Summons the bot to a voice channel.
        If no channel was specified, it joins your channel.
        """

        if not channel and not ctx.author.voice:
            raise VoiceError(ctx.lang["error"])

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name="leave", aliases=["disconnect"])
    @is_one_in_vc()
    async def _leave(self, ctx: StrapContext):
        """Clears the queue and leaves the voice channel."""

        if not ctx.voice_state.voice:
            raise NotPlayingError(ctx.lang["error"])

        await ctx.voice_state.stop()
        del self.bot.voice_states[ctx.guild.id]
        await ctx.message.add_reaction("👋🏻")

    @commands.command(name="now", aliases=["current", "playing", "np"])
    async def _now(self, ctx: StrapContext):
        """Displays the currently playing song."""

        await ctx.send(embed=ctx.voice_state.current.create_embed(ctx, nowcmd=True))

    @commands.command(name="pause", aliases=["resume"])
    @is_one_in_vc()
    async def _pause(self, ctx: StrapContext):
        """Pauses/Resumes the currently playing song."""

        if not ctx.voice_state.voice:
            raise RuntimeError("Nothing is being played right now.")

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            if ctx.invoked_with == "resume":
                raise NameError("Already playing")
            ctx.voice_state.voice.pause()
        else:
            ctx.voice_state.voice.resume()
        await ctx.message.add_reaction("⏯")

    @commands.command(name="stop")
    @is_one_in_vc()
    async def _stop(self, ctx: StrapContext):
        """Stops playing song and clears the queue."""

        ctx.voice_state.songs.clear()

        ctx.voice_state.voice.stop()
        await ctx.message.add_reaction("⏹")

    @commands.command(name="sotp", hidden=True)
    @is_one_in_vc()
    async def _sotp(self, ctx: StrapContext):
        """sotp"""
        ctx.voice_state.songs.clear()

        if ctx.voice_state.voice:
            ctx.voice_state.voice.stop()
        await ctx.message.add_reaction("<:sotp:806631974692978698>")

    @commands.command(name="skip")
    async def _skip(self, ctx: StrapContext):
        """Skips to the next song."""

        if not ctx.voice_state.is_playing:
            raise NotPlayingError(ctx.lang["error"])

        voter = ctx.author
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
                        title=ctx.lang.vote.voted,
                        description=ctx.lang.vote.success,
                        color=discord.Color.lighter_grey(),
                    ).add_field(name=ctx.lang.vote.current_, value=f"**{total_votes}**")
                )

        else:
            raise RuntimeError(ctx.lang["vote"]["error"])

    @commands.command(name="volume")
    async def _volume(self, ctx: StrapContext, *, volume: int = None):
        """Sets the player's volume."""

        if not ctx.voice_state.is_playing:
            return await ctx.send(ctx.lang["nothing"])

        if volume == None:
            return await ctx.send(
                ctx.lang["info"].format(
                    round(ctx.voice_state.current.source.volume * 100)
                )
            )

        if volume < 1 or volume > 100:
            raise ValueError(ctx.lang["error"])

        before = round(ctx.voice_state.current.source.volume * 100)
        ctx.voice_state.current.source.volume = volume / 100
        await self.db.find_one_and_update(
            {"_id": "volumes"}, {"$set": {str(ctx.guild.id): volume / 100}}, upsert=True
        )
        await ctx.send(
            embed=discord.Embed(
                title=ctx.lang.success,
                description=ctx.lang.done.format(volume),
                color=discord.Color.lighter_grey(),
            ).add_field(name=ctx.lang.before, value=f"{before}%")
        )

    @commands.command(name="queue")
    async def _queue(self, ctx: StrapContext):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """
        if len(ctx.voice_state.songs) == 0:
            raise ValueError(ctx.lang["error"])

        items_per_page = 10
        current_title = discord.utils.escape_markdown(
            ctx.voice_state.current.source.title
        )
        current = ctx.lang.current_.format(
            f"[{current_title}]({ctx.voice_state.current.source.url})"
        )

        pages = [
            ctx.voice_state.songs[i : i + items_per_page]
            for i in range(0, len(ctx.voice_state.songs), items_per_page)
        ]

        ret = []
        for n, page in enumerate(pages):
            queue = []
            for i, song in enumerate(page):
                if n != 0:
                    i = int(str(f"{n}{i}"))

                title = (
                    discord.utils.escape_markdown(song.source.title)
                    .replace("[", "(")
                    .replace("]", ")")
                )
                if len(title) >= 50:
                    title = "".join(list(title)[:50]) + "..."

                queue_to_append = f"`{i + 1}.` [**{title}**]({song.source.url})"
                queue.append(queue_to_append)

            ret.append(
                discord.Embed(
                    description=ctx.lang.tracks.format(
                        len(ctx.voice_state.songs), current, "\n".join(queue)
                    ),
                    color=discord.Color.lighter_grey(),
                )
            )

        await ctx.send(embeds=ret)

    @commands.command(name="shuffle")
    async def _shuffle(self, ctx: StrapContext):
        """Shuffles the queue."""

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(ctx.lang["error"])

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction("🔀")

    @commands.command(name="remove")
    async def _remove(self, ctx: StrapContext, index: int):
        """Removes a song from the queue at a given index."""

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(ctx.lang["error"])

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction("✅")

    @commands.command(name="loop")
    async def _loop(self, ctx: StrapContext):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """

        if not ctx.voice_state.is_playing:
            raise NotPlayingError(ctx.lang["error"])

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction("🔂" if ctx.voice_state.loop else "⏹️")

    @commands.command(name="play", aliases=["p"])
    async def _play(self, ctx: StrapContext, *, search: str = None):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """
        src = YTDLSource

        if (
            ctx.voice_state.is_playing
            and ctx.voice_state.voice.is_paused()
            and search == None
        ):
            return await ctx.invoke(self._pause)

        if not ctx.voice_state.voice:
            await ctx.invoke(self._summon)

        if search == None:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "search"})()
            )

        first = not ctx.voice_state.is_playing

        volume = (await self.db.find_one({"_id": "volumes"}) or {}).get(
            str(ctx.guild.id), 0.5
        )
        if isinstance(ctx.voice_state.voice.channel, discord.StageChannel):
            await ctx.guild.me.edit(suppress=False)

        async with ctx.typing():
            msg = await ctx.send(ctx.lang.fetching)
            result: dict = await self.bot.loop.run_in_executor(
                None, lambda: src.ytdl.extract_info(search, download=False)
            )
            if not result:
                raise YTDLError(ctx.lang.noresults.format(search))

            if not "entries" in result or isinstance(result, list):
                videos: list = result
            else:
                videos: list = result["entries"]

            if not videos:
                raise RuntimeError(ctx.lang.unfetchable.format(search))

            await msg.edit(content=ctx.lang.queueing)
            for video in videos:
                need_to_break = False
                if isinstance(videos, dict):
                    url = videos["webpage_url"]
                    need_to_break = True
                else:
                    url = video["webpage_url"]
                source: YTDLSource = await src.create_source(
                    ctx, url, loop=self.bot.loop
                )
                source.volume = volume
                song = Song(source, first=first)
                await ctx.voice_state.songs.put(song)
                if need_to_break:
                    break

            await msg.delete()
            await asyncio.sleep(0.1)
            ctx.voice_state.playedonce = True
            if "entries" in result and len(result["entries"]) > 1:
                await ctx.send(ctx.lang.queued.format(len(result["entries"])))
            elif not first:
                await ctx.send(
                    embed=song.create_embed(ctx, queued=True), reference=None
                )

    @commands.command(name="search")
    async def _search(self, ctx: StrapContext, *, search: str):
        """Searchs for a YouTube video."""
        async with ctx.typing():
            try:
                source = await YTDLSource.search_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                raise RuntimeError(str(e)) from e
            else:
                if source == "sel_invalid" or source == "timeout":
                    await ctx.send(ctx.lang[source])
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
    @_search.before_invoke
    async def ensure_voice_state(self, ctx: StrapContext):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError("You are not connected to any voice channel.")

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError("Bot is already in a voice channel.")


def setup(bot):
    bot.add_cog(Music(bot))
