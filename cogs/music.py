import os
import json
import re
import random
import discord
import lavalink
from discord.ext import commands
import asyncio
from box import Box, BoxKeyError
from functools import partial
from lavalink.models import DefaultPlayer
from core.languages import Language


class MusicError(Exception):
    pass


class YTDLData(Box):
    def __getattr__(self, *args, **kwargs):
        try:
            return super().__getattr__(*args, **kwargs)
        except BoxKeyError:
            pass

    def __getitem__(self, *args, **kwargs):
        try:
            return super().__getitem__(*args, **kwargs)
        except BoxKeyError:
            pass


class GuildsData(Box):
    def __getattr__(self, item, *args, **kwargs):
        try:
            return super().__getattr__(item, *args, **kwargs)
        except BoxKeyError:
            setattr(self, item, {})
            return getattr(self, item)

    def __getitem__(self, item, *args, **kwargs):
        try:
            return super().__getitem__(item, *args, **kwargs)
        except BoxKeyError:
            self[item] = {}
            return self[item]


url_rx = re.compile(r"https?://(?:www\.)?.+")


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
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db.get_cog_partition(self)
        self.guilds_data = GuildsData()
        lavalink.add_event_hook(self.track_hook)

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()

    async def cog_check(self, ctx):
        """ Command before-invoke handler. """
        guild_check = ctx.guild is not None
        #  This is essentially the same as `@commands.guild_only()`
        #  except it saves us repeating ourselves (and also a few lines).

        if guild_check:
            try:
                await self.ensure_voice(ctx)
            except MusicError as e:
                await ctx.send(e)
                return False

            #  Ensure that the bot and command author share a mutual voicechannel.
        else:
            await ctx.send("This command can't be run in DMs.")

        return guild_check

    def create_nowplaying_embed(
        self,
        source,
        player: DefaultPlayer,
        channel: discord.TextChannel,
        current=None,
        queued=False,
        nowcmd=False,
        is_first=False,
        lang=None,
        current_lang=None
    ):
        current = current or player.current
        titolo = discord.utils.escape_markdown(current.title)
        embed = discord.Embed(
            description=f"**[{titolo}]({current.uri})**",
            color=discord.Color.lighter_grey(),
        ).set_author(
            name=(lang.started if is_first and not nowcmd else lang.playing)
            if not queued
            else lang.enqueued,
            icon_url=self.bot.user.avatar_url,
        )
        if source.duration or player.current.duration:
            data = self.guilds_data[channel.guild.id]
            entire_duration = self.parse_duration(current.duration / 1000, current_lang)
            watched = self.parse_duration(data.watched, current_lang)
            unwatched = self.parse_duration(data.unwatched, current_lang)
            if nowcmd and data:
                embed.add_field(
                    name=lang.duration,
                    value=(
                        f"**```fix\n{data.text_watched}\n```**"
                        + lang.listened.format(entire_duration=entire_duration, watched=watched, duration=unwatched)
                        if data.duration != ""
                        else ""
                    )
                    if not current.stream
                    else "Live",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Duration",
                    value=entire_duration if not current.stream else "Live",
                    inline=False,
                )

        requester = channel.guild.get_member(current.requester)
        embed.add_field(name=lang.requester, value=requester.mention)
        if source.uploader:
            embed.add_field(
                name="Uploader",
                value=f"**[{current.author}]({source.uploader_url})**",
            )

        if source.like_count:
            embed.add_field(name=lang.likes, value=str(source.like_count))
        if source.dislike_count:
            embed.add_field(name=lang.dislikes, value=str(source.dislike_count))
        if source.view_count:
            embed.add_field(name=lang.views, value=str(source.view_count))

        thumbs = source.thumbnails
        if thumbs:
            embed.set_thumbnail(url=thumbs[-1].url)

        return embed  # TODO: translate this

    async def _update_time_watched(self, guild: discord.Guild, player: DefaultPlayer):
        #data = player.fetch("current_track_info")

        #while (
        #    round(self.guilds_data[guild.id].raw_duration or 0) != 0
        #    and player.is_playing
        #    and not (self.guilds_data[guild.id].skipped or False)
        #):
        symbols = "▬" * 20
        while player.is_playing and player.fetch("is_utw", False):
            
                position = player.position / 1000
                if player.paused:
                    await asyncio.sleep(0)
                    continue

                if player.current.stream:
                    self.guilds_data[guild.id].text_watched = (
                        "|" + symbols[:20] + "🔘" + "| [LIVE]"
                    )
                    await asyncio.sleep(0)
                    continue
                    

                duration_int = player.current.duration / 1000

                val = round(
                    (
                        (
                            100
                            * float(position)
                            / float(duration_int)
                        )
                        / 50
                    )
                    * 10
                )
                self.guilds_data[guild.id].text_watched = (
                    "|" + symbols[:val] + "🔘" + symbols[val:] + "| [BETA]"
                )
                self.guilds_data[guild.id].watched = position
                self.guilds_data[guild.id].unwatched = duration_int - position
                await asyncio.sleep(0)
        else:
                bound = self.guilds_data[guild.id].bound
                del self.guilds_data[guild.id]
                self.guilds_data[guild.id].bound = bound
            

    def parse_duration(self, duration: int, lang=None):
        lang = lang or self.bot.lang.default
        minutes, seconds = divmod(duration or 60, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        day, hour, minute, second = (
            "days" if days != 1 else "day",
            "hours" if hours != 1 else "hour",
            "minutes" if minutes != 1 else "minute",
            "seconds" if seconds != 1 else "second",
        )
        if lang == "it":
            day, hour, minute, second = (
                "giorni" if days != 1 else "giorno",
                "ore" if hours != 1 else "ora",
                "minuti" if minutes != 1 else "minuto",
                "secondi" if seconds != 1 else "secondo",
            )

        duration = []
        if days > 0:
            duration.append(f"{round(days)} {day}")
        if hours > 0:
            duration.append(f"{round(hours)} {hour}")
        if minutes > 0:
            duration.append(f"{round(minutes)} {minute}")
        if seconds > 0:
            duration.append(f"{round(seconds)} {second}")

        return ", ".join(duration)  # TODO: translate this

    @commands.command(name="now", aliases=["nowplaying", "playing", "np"])
    async def now_playing(self, ctx):
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        await ctx.send(
            embed=self.create_nowplaying_embed(
                YTDLData(player.fetch("current_track_info") or {}),
                player,
                ctx,
                nowcmd=True,
                lang=(await ctx.get_lang(cog=True)).now,
                current_lang=(await ctx.get_lang(cog=True)).current
            )
        )

    @commands.command(name="summon", aliases=["join"])
    async def summon_bot(self, ctx):
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.is_connected:
            return await ctx.send(ctx.lang.alr)

        await ctx.message.add_reaction("🆗")

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player: DefaultPlayer = self.bot.lavalink.player_manager.create(
            ctx.guild.id, endpoint=str(ctx.guild.region)
        )
        lang = (await ctx.get_lang(cog=True)).ensure_voice

        should_connect = ctx.command.name in ("play", "playfromlist", "summon")

        if not ctx.author.voice or not ctx.author.voice.channel:
            # Our cog_command_error handler catches this and sends it to the voicechannel.
            # Exceptions allow us to "short-circuit" command invocation via checks so the
            # execution state of the command goes no further.
            raise MusicError(lang.join)

        if not player.is_connected:
            if not should_connect:
                raise MusicError(lang.notconnected)

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                raise MusicError(lang.perms)

            player.store("channel", ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise MusicError(lang.samevc)

    @commands.command(name="play")
    @is_one_in_vc()
    async def play_song(self, ctx, *, query=None):
        # Get the player for this guild from cache.
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if (
            player.is_playing
            and player.paused
            and query == None
        ):
            return await ctx.invoke(self.pause_bot)
        
        if query == None:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "query"})()
            )

        volume = (await self.db.find_one({"_id": "volumes"}) or {}).get(
            str(ctx.guild.id), 100
        )
        oquery = query
        query = query.strip("<>")
        # Check if the user input might be a URL.
        if not url_rx.match(query):
            query = f"ytsearch:{query}"

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        # Results could be None if Lavalink returns an invalid response (non-JSON/non-200 (OK)).
        # ALternatively, resullts['tracks'] could be an empty array if the query yielded no tracks.
        if not results or not results["tracks"]:
            return await ctx.send(ctx.lang.noresults)

        self.guilds_data[ctx.guild.id].is_first = is_first = len(player.queue) == 0 and not player.current
        self.guilds_data[ctx.guild.id].bound = ctx.channel
        coso = False

        # Valid loadTypes are:
        #   TRACK_LOADED    - single video/direct URL)
        #   PLAYLIST_LOADED - direct URL to playlist)
        #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
        #   NO_MATCHES      - query yielded no results
        #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
        if results["loadType"] == "PLAYLIST_LOADED":  # This handles playlist links
            tracks = results["tracks"]

            for track in tracks:
                # Add all of the tracks from the playlist to the queue.
                player.add(requester=ctx.author.id, track=track)
            
            coso = True
            await ctx.send(ctx.lang.queued.format(len(tracks)))

        else:
            track = results["tracks"][0]

            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
            player.add(requester=ctx.author.id, track=track)

        current = player.current if is_first else player.queue[-1]

        if not player.is_playing:
            await player.set_volume(volume)
            await player.play()
        elif not coso:
            await ctx.send(ctx.lang.onequeued.format(current.title, current.author))

    @commands.command(name="skip")
    async def _skip(self, ctx):
        """Skips to the next song."""
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(
            ctx.guild.id
        )
        if not player.is_playing:
            return await ctx.send(ctx.lang["error"])

        voter = ctx.author
        if not "skip_votes" in self.guilds_data[ctx.guild.id]:
            self.guilds_data[ctx.guild.id].skip_votes = set()
        #if voter == player.current.requester:
        #    await player.skip()
        #    await ctx.message.add_reaction("⏭")

        if voter.id not in self.guilds_data[ctx.guild.id].skip_votes:
            self.guilds_data[ctx.guild.id].skip_votes.add(voter.id)
            total_votes = len(self.guilds_data[ctx.guild.id].skip_votes)

            users = 0
            channel = await self.bot.fetch_channel(player.channel_id)
            for u in channel.members:
                if not u.bot:
                    users += 1

            async def do_skip():
                self.guilds_data[ctx.guild.id].skip_votes.clear()
                await ctx.message.add_reaction("⏭")
                await player.skip()

            if ctx.channel.permissions_for(ctx.author).manage_channels:
                return await do_skip()
            elif "dj" in [r.name.lower() for r in ctx.author.roles]:
                return await do_skip()
            elif total_votes >= (users - 1 if users > 2 else users):
                return await do_skip()
            else:
                await ctx.send(
                    embed=discord.Embed(
                        title=ctx.lang.vote.voted,
                        description=ctx.lang.vote.success,
                        color=discord.Color.lighter_grey(),
                    ).add_field(name=ctx.lang.vote.current_, value=f"**{total_votes}**")
                )

        else:
            await ctx.send(ctx.lang["vote"]["error"])

    @commands.command(name="leave")
    @is_one_in_vc()
    async def clear_queue(self, ctx):
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player and ctx.author.voice is not None and ctx.author.voice.channel.id == int(
            player.channel_id
        ):
            player.queue.clear()
            await player.stop()
            await ctx.guild.change_voice_state(channel=None)
            await ctx.message.add_reaction("👋🏻")
        else:
            await ctx.message.add_reaction("❌")

    @commands.command(name="stop")
    @is_one_in_vc()
    async def stop(self, ctx):
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player and ctx.author.voice is not None and ctx.author.voice.channel.id == int(
            player.channel_id
        ):
            player.queue.clear()
            await player.stop()
            await ctx.message.add_reaction("⏹")
        else:
            await ctx.message.add_reaction("❌")

    @commands.command(name="sotp", hidden=True)
    @is_one_in_vc()
    async def sotp(self, ctx):
        """sotp"""
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player and ctx.author.voice is not None and ctx.author.voice.channel.id == int(
            player.channel_id
        ):
            player.queue.clear()
            await player.stop()
        await ctx.message.add_reaction("<:sotp:806631974692978698>")

    @commands.command(name="volume")
    async def _volume(self, ctx, *, volume: int = None):
        """Sets the player's volume."""
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.message.add_reaction("❌")

        if not player.is_playing:
            return await ctx.send(ctx.lang["nothing"])

        if volume == None:
            return await ctx.send(
                ctx.lang["info"].format(
                    round(player.volume)
                )
            )

        if volume < 1 or volume > 100:
            return await ctx.send(ctx.lang["error"])

        before = round(player.volume)
        await player.set_volume(volume)
        await self.db.find_one_and_update(
            {"_id": "volumes"}, {"$set": {str(ctx.guild.id): volume}}, upsert=True
        )
        await ctx.send(
            embed=discord.Embed(
                title=ctx.lang.success,
                description=ctx.lang.done.format(volume),
                color=discord.Color.lighter_grey(),
            ).add_field(name=ctx.lang.before, value=f"{before}%")
        )

    @commands.command(name="pause", aliases=["resume"])
    @is_one_in_vc()
    async def pause_bot(self, ctx):
        # try:
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return

        if not player.is_playing:
            await ctx.channel.send(ctx.lang.error)

        if ctx.invoked_with == "resume" and not player.paused:
            return await ctx.send(ctx.lang.notpaused)

        toggle = not player.paused
        await player.set_pause(toggle)
        await ctx.message.add_reaction("⏯")

    # except:
    #    await ctx.channel.send("Nothing playing.")

    @commands.command(name="queue")
    async def _queue(self, ctx):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player.is_playing:
            return

        if len(player.queue) == 0:
            raise ValueError(ctx.lang["error"])

        items_per_page = 10
        current_title = discord.utils.escape_markdown(
            player.current.title
        )
        current = ctx.lang.current_.format(
            f"[{current_title}]({player.current.uri})"
        )

        pages = [
            player.queue[i : i + items_per_page]
            for i in range(0, len(player.queue), items_per_page)
        ]

        ret = []
        for n, page in enumerate(pages):
            queue = []
            for i, song in enumerate(page):
                if n != 0:
                    i = int(str(f"{n}{i}"))

                title = (
                    discord.utils.escape_markdown(song.title)
                    .replace("[", "(")
                    .replace("]", ")")
                )
                if len(title) >= 50:
                    title = "".join(list(title)[:50]) + "..."

                queue_to_append = f"`{i + 1}.` [**{title}**]({song.uri})"
                queue.append(queue_to_append)

            ret.append(
                discord.Embed(
                    description=ctx.lang.tracks.format(
                        len(player.queue), current, "\n".join(queue)
                    ),
                    color=discord.Color.lighter_grey(),
                )
            )

        await ctx.send(embeds=ret)

    # This needs to be tested more thoroughly. Believe to have solved it but unsure.
    @commands.command(name="shuffle")
    @is_one_in_vc()
    async def shuffle(self, ctx):
        player: DefaultPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return
        if player.is_playing:
                songlist = list(player.queue) # defined the list class to make a new object completely different from the queue
                if not songlist:
                    return await ctx.send(ctx.lang.error)
                random.shuffle(songlist) # This breaks my bot at times.. Custom shuffle to slow this down.
                player.queue = songlist
                await asyncio.sleep(0.1)
                await ctx.message.add_reaction("🔀")
        else:
                await ctx.channel.send(ctx.lang.notplaying)

    # This function has not been updated to the latest API and is not currently recommended. May add back in a future update.
    # @commands.command(name = 'clearbotcache', description="Used to clear the bot cache, only use after reading the Readme file. This can have negative consequences and should be avoided.")
    # @commands.has_permissions(ban_members=True, kick_members=True, manage_roles=True, administrator=True)
    # async def disconnect_player(self, ctx):
    #    player: DefaultPlayer = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
    #    await self.bot.lavalink.player_manager.destroy(int(ctx.guild.id))
    #    await ctx.channel.send("Bot player has been cleared successfully.")

    async def send_msg(self, player, channel, current, is_first, lang, current_lang):
        while not player.is_playing:
            await asyncio.sleep(0)

        def create_embed():
            return self.create_nowplaying_embed(
                YTDLData(player.fetch("current_track_info") or {}),
                player,
                channel,
                current=current,
                queued=False,
                is_first=is_first,
                lang=lang,
                current_lang=current_lang
            )

        m = await channel.send(embed=create_embed())

        data = player.fetch("current_track_info", None)
        while data == None:
            data = player.fetch("current_track_info", None)
            await asyncio.sleep(1)

        await m.edit(embed=create_embed())

    async def track_hook(self, event):

        if isinstance(event, lavalink.events.TrackStartEvent):
            cls = self.__class__.__name__
            db = self.bot.db.db["Config"]
            guilds = await db.find_one({"_id": "guilds"})
            if str(event.player.guild_id) in guilds:
                current_lang = guilds[str(event.player.guild_id)].get("language", self.bot.lang.default)
            else:
                current_lang = self.bot.lang.default

            lang = json.load(open(f"core/languages/{current_lang}.json"))

            lang = lang.get("cogs", {}).get(cls, {})

            lang["current"] = current_lang
            lang = Language(lang)

            async def alt_upd():
                return

            async def get_info():
                data = None
                event.player.delete("current_track_info")
                old = event.player.fetch("current_track_info")
                while data == None or data == old:
                    data = await self.bot.loop.run_in_executor(
                        None,
                        partial(
                            self.bot.ytdl.extract_info,
                            event.player.current.uri,
                            download=False,
                            process=False,
                        ),
                    )
                event.player.store("current_track_info", data)

            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            channel = self.guilds_data[guild.id].bound
            upd = alt_upd()
            duration_int = event.player.current.duration / 1000
            self.guilds_data[guild.id].duration = duration_int
            self.guilds_data[guild.id].entire_duration = self.parse_duration(duration_int, lang.current)
            if not event.player.fetch("is_utw", False):
                await upd # so python doesnt warn it hasn't been awaited
                event.player.store("is_utw", True)
                upd = self._update_time_watched(guild, event.player)
            is_first = self.guilds_data[guild.id].is_first

            await asyncio.gather(get_info(), upd, self.send_msg(event.player, channel, event.player.current, is_first, lang.now, lang.current))
        elif isinstance(event, lavalink.events.QueueEndEvent):
            # When this track_hook receives a "QueueEndEvent" from lavalink.py
            # it indicates that there are no tracks left in the player's queue.
            # To save on resources, we can tell the bot to disconnect from the voicechannel.
            event.player.delete("is_utw")
            event.player.delete("current_track_info")
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            self.guilds_data[guild.id].skipped = True
            await guild.change_voice_state(channel=None)


def setup(bot):
    bot.add_cog(Music(bot))
