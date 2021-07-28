import re
import asyncio
import discord
import random
import functools
import itertools
import youtube_dl
import ffmpeg
from discord.ext import commands
from async_timeout import timeout
from core.logs import get_logger_instance

# Silence useless bug reports messages
youtube_dl.utils.bug_reports_message = lambda: ""


class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class NotPlayingError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    logger = get_logger_instance()
    YTDL_OPTIONS = {
        "logger": logger,
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
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

    ffmpeg = ffmpeg.FFmpeg()
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
            self.upload_date = (
                self.upload_date[6:8]
                + "."
                + self.upload_date[4:6]
                + "."
                + self.upload_date[0:4]
            )

        self.title = str(data.get("title"))
        self.escaped_title = discord.utils.escape_markdown(self.title)
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
        return f"**{self.escaped_title}**" + (
            f" by **{self.uploader}**" if self.uploader != None else ""
        )

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

        try:
            webpage_url = process_info["webpage_url"]
        except KeyError:
            raise YTDLError("Playlists aren't supported yet. :(")
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

        cls.search_query = "%s%s:%s" % ("ytsearch", 10, "".join(search))

        partial = functools.partial(
            cls.ytdl.extract_info, cls.search_query, download=False, process=False
        )
        info = await loop.run_in_executor(None, partial)

        cls.search = {}
        cls.search["title"] = f"{ctx.lang['results']}:\n**{search}**"
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

        lst.append(ctx.lang["choose"])
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
                    data = {}
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
            duration.append(f"{round(days)} day{day}")
        if hours > 0:
            duration.append(f"{round(hours)} hour{hour}")
        if minutes > 0:
            duration.append(f"{round(minutes)} minute{minute}")
        if seconds > 0:
            duration.append(f"{round(seconds)} second{second}")

        return ", ".join(duration)  # TODO: translate this


class Song:
    __slots__ = ("source", "requester", "is_first")

    def __init__(self, source: YTDLSource, first: bool = False):
        self.source: YTDLSource = source
        self.requester = source.requester
        self.is_first = first

    def create_embed(self, ctx, queued=False, nowcmd=False):
        embed = discord.Embed(
            description="**[{0.source.escaped_title}]({0.source.url})**".format(self),
            color=discord.Color.lighter_grey(),
        ).set_author(
            name=("Started" if self.is_first and not nowcmd else "Now") + " playing"
            if not queued
            else "Enqueued",
            icon_url=self.source.ctx.bot.user.avatar_url,
        )
        if self.source.duration:
            if nowcmd:
                embed.add_field(
                    name="Duration",
                    value=(
                        f"**```fix\n{ctx.voice_state.text_watched}\n```**"
                        f"{ctx.voice_state.watched} listened of {self.source.duration}."
                        f"\n{ctx.voice_state.duration} remaining."
                        if ctx.voice_state.duration != ""
                        else ""
                    ),
                    inline=False,
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
            embed.add_field(name="Dislikes", value=str(self.source.dislikes))
        if self.source.views:
            embed.add_field(name="Views", value=str(self.source.views))

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

        self.current: Song = None
        self.voice: discord.VoiceClient = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.playedonce = False

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()
        self.raw_watched = None
        self.watched = None
        self.text_watched = None
        self.duration = None
        self.raw_duration = None
        self.is_skipped = False

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
                    if self.playedonce:
                        async with timeout(180):  # 3 minutes
                            self.current = await self.songs.get()
                    else:
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    del self.bot.voice_states[self._ctx.guild.id]
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

        while round(self.raw_duration) != 0 and self.is_playing and not self.is_skipped:
            self.raw_duration -= 1
            self.raw_watched = self.current.source.raw_duration - self.raw_duration
            val = round(
                (
                    (
                        100
                        * float(self.raw_watched)
                        / float(self.current.source.raw_duration)
                    )
                    / 50
                )
                * 10
            )
            symbols = "▬" * 20
            self.text_watched = "|" + symbols[:val] + "🔘" + symbols[val:] + "|"
            self.watched = YTDLSource.parse_duration(self.raw_watched)
            self.duration = YTDLSource.parse_duration(self.raw_duration)

            __import__("time").sleep(1)
        else:
            self.watched = None
            self.is_skipped = False

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error)) from error

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()
        self.is_skipped = True

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None
