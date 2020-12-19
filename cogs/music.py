# -*- coding: utf-8 -*-


import functools
import itertools
import math
import random
import youtube_dl
import asyncio
import discord
from discord.ext import commands
from async_timeout import timeout

# Silence useless bug reports messages
youtube_dl.utils.bug_reports_message = lambda: ""


def is_one_in_vc():
    async def check(ctx):
        users = 0
        if ctx.voice_client:
            for u in ctx.voice_client.channel.members:
                if not u.bot:
                    users += 1

        if users == 1:
            return True
        if ctx.channel.permissions_for(ctx.author).manage_guild:
            return True
        else:
            raise commands.MissingPermissions(["Manage Server"])

    return commands.check(check)


class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass

class NotPlayingError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
    }

    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)
    ytdl.cache.remove()

    def __init__(
        self,
        ctx: commands.Context,
        source: discord.FFmpegPCMAudio,
        *,
        data: dict,
        volume: float = 0.5,
    ):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data
        self.ctx = ctx

        self.uploader = data.get("uploader")
        self.uploader_url = data.get("uploader_url")
        self.upload_date = data.get("upload_date")
        if self.upload_date != None:
            self.upload_date = self.upload_date[6:8] + "." + self.upload_date[4:6] + "." + self.upload_date[0:4]

        self.title = discord.utils.escape_markdown(str(data.get("title")))
        self.thumbnail = data.get("thumbnail")
        self.description = data.get("description")
        self.raw_duration = data.get("duration")
        if self.raw_duration != None:
            self.duration = self.parse_duration(int(self.raw_duration))
        else:
            self.duration = self.raw_duration

        self.tags = data.get("tags")
        self.url = data.get("webpage_url")
        self.views = data.get("view_count")
        self.likes = data.get("like_count")
        self.dislikes = data.get("dislike_count")
        self.stream_url = data.get("url")

    def __str__(self):
        return f"**{self.title}**" + (f" by **{self.uploader}**" if self.uploader != None else "")

    @classmethod
    async def create_source(
        cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None
    ):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(
            cls.ytdl.extract_info, search, download=False, process=False
        )
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError("Couldn't find anything that matches `{}`".format(search))

        if "entries" not in data:
            process_info = data
        else:
            process_info = None
            for entry in data["entries"]:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError(
                        "Couldn't find anything that matches `{}`".format(search)
                )

        webpage_url = process_info["webpage_url"]
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError("Couldn't fetch `{}`".format(webpage_url))

        if "entries" not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info["entries"].pop(0)
                except IndexError:
                    raise YTDLError(
                        "Couldn't retrieve any matches for `{}`".format(webpage_url)
                    )

        return cls(
            ctx, discord.FFmpegPCMAudio(info["url"], **cls.FFMPEG_OPTIONS), data=info
        )

    @classmethod
    async def search_source(
        cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None
    ):
        bot = ctx.bot
        channel = ctx.channel
        loop = loop or asyncio.get_event_loop()
        lang = await ctx.get_lang(ctx.command.cog)

        cls.search_query = "%s%s:%s" % ("ytsearch", 10, "".join(search))

        partial = functools.partial(
            cls.ytdl.extract_info, cls.search_query, download=False, process=False
        )
        info = await loop.run_in_executor(None, partial)

        cls.search = {}
        cls.search["title"] = f"{lang['results']}:\n**{search}**"
        cls.search["type"] = "rich"
        cls.search["color"] = 7506394
        cls.search["author"] = {
            "name": f"{ctx.author.name}",
            "url": f"{ctx.author.avatar_url}",
            "icon_url": f"{ctx.author.avatar_url}",
        }

        lst = []
        entries = []

        for e in info["entries"]:
            entries.append(e)

        for i, e in enumerate(entries):
            # lst.append(f'`{info["entries"].index(e) + 1}.` {e.get("title")} **[{YTDLSource.parse_duration(int(e.get("duration")))}]**\n')
            VId = e.get("id")
            VUrl = "https://www.youtube.com/watch?v=%s" % (VId)
            lst.append(f'`{i + 1}.` [{e.get("title")}]({VUrl})\n')

        lst.append(lang["choose"])
        cls.search["description"] = "\n".join(lst)

        em = discord.Embed.from_dict(cls.search)
        em.color = discord.Color.lighter_grey()
        emb = await ctx.send(embed=em, delete_after=45.0)

        def check(msg):
            return (
                msg.content.isdigit() == True
                and msg.channel == channel
                or msg.content.lower() == "cancel"
            )

        try:
            m = await bot.wait_for("message", check=check, timeout=45.0)

        except asyncio.TimeoutError:
            rtrn = "timeout"

        else:
            if m.content.isdigit() == True:
                sel = int(m.content)
                if 0 < sel <= 10:

                    for e in entries:
                        if e == entries[sel - 1]:
                            VId = e["id"]
                            VUrl = "https://www.youtube.com/watch?v=%s" % (VId)
                            partial = functools.partial(
                                cls.ytdl.extract_info, VUrl, download=False
                            )
                            data = await loop.run_in_executor(None, partial)
                    rtrn = cls(
                        ctx,
                        discord.FFmpegPCMAudio(data["url"], **cls.FFMPEG_OPTIONS),
                        data=data,
                    )
                else:
                    rtrn = "sel_invalid"
            elif m.content.lower() == "cancel":
                rtrn = "cancel"
                await emb.delete()
            else:
                rtrn = "sel_invalid"

        return rtrn

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        day, hour, minute, second = (
            "s" if days != 1 else "",
            "s" if hours != 1 else "",
            "s" if minutes != 1 else "",
            "s" if seconds != 1 else "",
        )

        duration = []
        if days > 0:
            duration.append(f"{days} day{day}")
        if hours > 0:
            duration.append(f"{hours} hour{hour}")
        if minutes > 0:
            duration.append(f"{minutes} minute{minute}")
        if seconds > 0:
            duration.append(f"{seconds} second{second}")

        return ", ".join(duration) # TODO: translate this


class Song:
    __slots__ = ("source", "requester", "is_first")

    def __init__(self, source: YTDLSource, first: bool=False):
        self.source = source
        self.requester = source.requester
        self.is_first = first

    def create_embed(self, ctx, nowcmd=False):
        embed = discord.Embed(
            description="**[{0.source.title}]({0.source.url})**".format(self),
            color=discord.Color.lighter_grey(),
        ).set_author(
            name=("Started" if self.is_first and not nowcmd else "Now") + " playing",
            icon_url=self.source.ctx.bot.user.avatar_url
        )
        if self.source.duration:
            if nowcmd:
                embed.add_field(
                    name="Duration",
                    value=(
                        f"**```fix\n{ctx.voice_state.text_watched}\n```**"
                        f"{ctx.voice_state.watched} listened of {self.source.duration}."
                        f"\n{ctx.voice_state.duration} remaining." if ctx.voice_state.duration != "" else ""
                    ),
                    inline=False
                )
            else:
                embed.add_field(name="Duration", value=self.source.duration)
        embed.add_field(name="Requested by", value=self.requester.mention)
        if self.source.uploader:
            embed.add_field(
                name="Uploader",
                value="**[{0.source.uploader}]({0.source.uploader_url})**".format(self),
            )
        
        if self.source.likes:
            embed.add_field(name="Likes", value=str(self.source.likes))
        if self.source.dislikes:
            embed.add_field(
                name="Dislikes", value=str(self.source.dislikes)
            )
        if self.source.views:
            embed.add_field(
                name="Views", value=str(self.source.views)
            )

        if self.source.thumbnail:
            embed.set_thumbnail(url=self.source.thumbnail)

        return embed  # TODO: translate this


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.exists = True

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()
        self.raw_watched = None
        self.watched = None
        self.text_watched = None
        self.duration = None
        self.raw_duration = None

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            self.now = None

            if self.loop == False:
                # Try to get the next song within 3 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False

                    return

                self.current.source.volume = self._volume
                self.voice.play(self.current.source, after=self.play_next_song)
                await self.current.source.channel.send(
                    embed=self.current.create_embed(self._ctx)
                )
            # If the song is looped
            elif self.loop == True:
                self.now = discord.FFmpegPCMAudio(
                    self.current.source.stream_url, **YTDLSource.FFMPEG_OPTIONS
                )
                self.voice.play(self.now, after=self.play_next_song)

            await self.bot.loop.run_in_executor(None, self._update_time_watched)

            await self.next.wait()

    def _update_time_watched(self):
        self.raw_duration = self.current.source.raw_duration

        while round(self.raw_duration) != 0 and self.is_playing:
            self.raw_duration -= 1
            self.raw_watched = self.current.source.raw_duration - self.raw_duration
            val = round(((100 * float(self.raw_watched)/float(self.current.source.raw_duration)) / 50) * 10)
            symbols = "▬" * 20
            self.text_watched = "|" + symbols[:val] + "🔘" + symbols[val:] + "|"
            self.watched = YTDLSource.parse_duration(self.raw_watched)
            self.duration = YTDLSource.parse_duration(self.raw_duration)

            __import__("time").sleep(1)
        else:
            self.watched = None

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error)) from error

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db.get_cog_partition(self)
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                "This command can't be used in DM channels."
            )

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    @commands.command(name="summon", aliases=["join"])
    async def _summon(
        self, ctx: commands.Context, *, channel: discord.VoiceChannel = None
    ):
        """Summons the bot to a voice channel.
        If no channel was specified, it joins your channel.
        """
        lang = await ctx.get_lang(self)

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
        lang = await ctx.get_lang(self)

        if not ctx.voice_state.voice:
            raise NotPlayingError(lang["error"])

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

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

        if not ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction("⏹")

    @commands.command(name="skip")
    async def _skip(self, ctx: commands.Context):
        """Skips to the next song."""
        lang = await ctx.get_lang(self)

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
                        color=discord.Color.lighter_grey()
                    ).add_field(
                        name=lang.vote.current,
                        value=f"**{total_votes}**"
                    )
                )

        else:
            raise RuntimeError(lang["vote"]["error"])

    @commands.command(name="volume")
    async def _volume(self, ctx: commands.Context, *, volume: int = None):
        """Sets the player's volume."""

        lang = await ctx.get_lang(self)

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
                color=discord.Color.lighter_grey()
            ).add_field(
                name=lang.before,
                value=f"{before}%"
            )
        )

    @commands.command(name="queue")
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """
        lang = await ctx.get_lang(self)

        if len(ctx.voice_state.songs) == 0:
            raise VaueError(lang["error"])

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
            color=discord.Color.lighter_grey()
        ).set_footer(text=lang["pages"].format(page, pages))
        await ctx.send(embed=embed)

    @commands.command(name="shuffle")
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""
        lang = await ctx.get_lang(self)

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(lang["error"])

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction("✅")

    @commands.command(name="remove")
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""
        lang = await ctx.get_lang(self)

        if len(ctx.voice_state.songs) == 0:
            raise ValueError(lang["error"])

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction("✅")

    @commands.command(name="loop")
    async def _loop(self, ctx: commands.Context):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """
        lang = await ctx.get_lang(self)

        if not ctx.voice_state.is_playing:
            raise NotPlayingError(lang["error"])

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction("🔂" if ctx.voice_state.loop else "⏹️")

    @commands.command(name="play", aliases=["p"])
    async def _play(self, ctx: commands.Context, *, search: str):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            return await ctx.invoke(self._resume)

        lang = await ctx.get_lang(self)
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

    @commands.command(name="search")
    async def _search(self, ctx: commands.Context, *, search: str):
        """Searchs for a YouTube video."""
        lang = await ctx.get_lang(self)
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
