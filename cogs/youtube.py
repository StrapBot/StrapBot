import discord
import os
import asyncio

from googleapiclient import discovery

from core.paginator import EmbedPaginatorSession
from functools import partial

# this isnt going to be rewritten for slash because
# I wanted to make it like /config but Discrod devs
# haven't implemented channel select menus yet, and
# it looks bad if I only change the commands module
# so I'm not rewriting this until they implement it
from discord.ext import commands


class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        self.db = self.bot.config.db
        self._client_connected = asyncio.Event()

    async def fetch_channels(self, name: str, limit: int = 10):

        await self._client_connected.wait()

        request = await self.bot.loop.run_in_executor(
            None,
            partial(
                self.client.search().list,
                part="snippet",
                q=name,
                type="channel",
                maxResults=limit,
            ),
        )

        request2 = await self.bot.loop.run_in_executor(
            None,
            partial(self.client.channels().list, part="snippet", id=name, maxResults=1),
        )

        response = await self.bot.loop.run_in_executor(None, request.execute)
        response2 = await self.bot.loop.run_in_executor(None, request2.execute)

        return response.get("items") or response2.get("items", [])

    async def fetch_channel(self, name: str):
        return ((await self.fetch_channels(name, 1)) or [None])[0]

    @commands.Cog.listener()
    async def on_connect(self):
        self.client = await self.bot.loop.run_in_executor(
            None,
            partial(
                discovery.build,
                "youtube",
                "v3",
                developerKey=os.getenv("GOOGLE_API_KEY"),
            ),
        )
        self._client_connected.set()

    @commands.command(usage="<add|remove/delete|list> <channel> [youtuber]")
    async def youtube(
        self,
        ctx,
        action: str = None,
        channel: discord.TextChannel = None,
        youtuber: str = None,
    ):
        error = None
        if action == "delete":
            action = "remove"
        elif action == "setmsg":
            action = "editmsg"
        elif action == "set_msg":
            action = "editmsg"
        elif action == "edit_msg":
            action = "editmsg"

        if action not in ["add", "remove", "list", "editmsg"]:
            error = "You must specify whether to `add`/`delete` a channel, `list` YouTubers or `editmsg`."
        elif not channel:
            error = "You must specify a channel."
        elif action != "list" and not youtuber:
            error = "You must specify a YouTuber."
        else:
            if action in ["add", "remove"]:
                youtubers = await self.fetch_channels(youtuber)
                if not youtubers:
                    error = "No YouTubers found."

        if error:
            await ctx.send(
                embed=discord.Embed(
                    title="Error", description=error, color=discord.Color.red()
                )
            )
            return

        req_url = str(os.getenv("STRAPBOT_API_URL")).rstrip("/")

        if not (req_url.startswith("http") or req_url.startswith("https")):
            req_url = f"http://{req_url}"

        if action in ["add", "remove"]:
            # made a list because else it would have created
            # a local variable inside the function
            result = []

            async def abort(session: EmbedPaginatorSession):
                await session.base.edit(
                    embed=discord.Embed(
                        title="Aborted", color=discord.Color.lighter_gray()
                    )
                )
                await session.close(delete=False)
                for _ in range(2):
                    result.append(False)

            async def choose_yter(session: EmbedPaginatorSession):
                result.append(youtubers[session.current])
                await session.base.clear_reactions()
                await session.close(delete=False)
                result.append(session.base)

            reactions = {"🛑": abort, "✅": choose_yter}
            if len(youtubers) > 1:
                embeds = []
                for yter in youtubers:
                    yter = yter["snippet"]
                    chid = yter["channelId"]
                    embeds.append(
                        discord.Embed(
                            color=discord.Color.lighter_gray(),
                            title=yter["title"],
                            description="If it's not in this list, please send the channel URL.",
                            url=f"https://youtube.com/channel/{chid}",
                        )
                        .set_author(
                            name="Choose a YouTuber", icon_url=ctx.me.avatar_url
                        )
                        .set_thumbnail(url=yter["thumbnails"]["high"]["url"])
                    )

                session = EmbedPaginatorSession(ctx, *embeds, reactions=reactions)
                await session.run()
                ytchannel = result[0]["snippet"]
                message = result[1]
                channelid = ytchannel["channelId"]
                if not ytchannel:
                    return
            else:
                channelid = youtubers[0]["id"]["channelId"]
                ytchannel = youtubers[0]["snippet"]
                message = await ctx.send(
                    embed=discord.Embed(color=discord.Color.orange()).set_footer(
                        text="Please wait...", icon_url=ctx.me.avatar_url
                    )
                )

            config = await self.bot.config.db.find_one({"_id": "youtube"}) or {}

            if not channelid in config:
                config[channelid] = []

            if not channel.id in config[channelid] and action == "remove":
                await ctx.send(
                    embed=discord.Embed(
                        title="Error",
                        description="This YouTuber wasn't added.",
                        color=discord.Color.red(),
                    )
                )
                return

            if channel.id in config[channelid] and action == "add":
                await ctx.send(
                    embed=discord.Embed(
                        title="Error",
                        description="This YouTuber is already added to the channel.",
                        color=discord.Color.red(),
                    )
                )
                return

            if action == "add":
                await self.bot.config.db.find_one_and_update(
                    {"_id": "youtube_messages"},
                    {"$set": {f"{channelid}_{channel.id}": "<link>"}},
                )

            config[channelid] = set(config[channelid])

            getattr(config[channelid], action)(channel.id)

            config[channelid] = list(config[channelid])
            await self.bot.config.db.find_one_and_update(
                {"_id": "youtube"}, {"$set": config}, upsert=True
            )

            data = {
                "hub.callback": f"{req_url}/updat",
                "hub.topic": f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channelid}",
                "hub.verify": "sync",
                "hub.mode": f"{'un' if action == 'remove' else ''}subscribe",
                "hub.verify_token": "",
                "hub.secret": "",
                "hub.lease_seconds": "",
            }
            req = await self.bot.session.post(
                "https://pubsubhubbub.appspot.com/subscribe", data=data
            )

            try:
                req.raise_for_status()
            except Exception:
                await message.edit(
                    embed=discord.Embed(
                        title="Error",
                        description="An unknown error occurred. Please try again later.",
                        color=discord.Color.red(),
                    )
                )
                raise
            else:
                await message.edit(
                    embed=discord.Embed(
                        color=discord.Color.lighter_gray(),
                        description=f"Updates from this channel will be announced in {channel.mention}."
                        if action == "add"
                        else "Updates from this channel will no longer be announced.",
                    ).set_author(name="Success", icon_url=ctx.me.avatar_url)
                )


def setup(bot):
    bot.add_cog(YouTube(bot))
