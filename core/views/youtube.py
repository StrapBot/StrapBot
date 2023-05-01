import os
from aiohttp.client_reqrep import ClientResponse, RequestInfo
from aiohttp.typedefs import LooseHeaders
import discord
import typing
from ..context import StrapContext
from datetime import datetime, timedelta
from discord import Embed, Interaction
from discord import ui
from enum import Enum
from typing import Optional, Tuple
from urllib.parse import urlencode
from aiohttp import ClientResponseError
from discord import ChannelType
from . import View, PaginationView, StopButton


class SearchType(Enum):
    channels = 0
    id = -1
    search = 1


class BackButton(StopButton):
    def __init__(self, view: "YouTubeView", emoji: str = "⬅️"):
        self.bview = view
        super().__init__(emoji)

    async def callback(self, interaction: Interaction[discord.Client]):
        await interaction.response.edit_message(
            content=self.bview.content, embed=None, view=self.bview
        )
        self.view.stop()


class PubSubHubbubResponseError(ClientResponseError):
    def __init__(
        self,
        request_info: RequestInfo,
        history: Tuple[ClientResponse, ...],
        *,
        code: Optional[int] = None,
        status: Optional[int] = None,
        message: str = "",
        headers: Optional[LooseHeaders] = None,
    ) -> None:
        super().__init__(
            request_info,
            history,
            code=code,
            status=status,
            message=message,
            headers=headers,
        )
        self.args = (
            "PubSubHubbub request failed",
            request_info.real_url,
            request_info.method,
            self.status,
            message,
            headers,
        )
        if history:
            self.args += (history,)

    def __str__(self):
        return f"PubSubHubbub request failed, code={super().__str__()}"


class ChannelsPaginator(PaginationView):
    def __init__(self, results: list, **kwargs):
        self.results = results
        pages = [discord.Embed(title=x["snippet"]["title"], description=x["snippet"]["description"]) for x in results]
        super().__init__(*pages, **kwargs)

    @ui.button(label="Choose")
    async def salve(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        youtuber = self.results[self.current]
        channel: discord.TextChannel = self.ctx.bot.get_channel(  #  type: ignore
            self.ctx.guild_config.yt_news_channel_id
        )

        try:
            await self.ctx.bot.request_pubsubhubbub(youtuber["id"], True)
            db = self.ctx.bot.get_db("YouTubeNews", False)
            channel_db = (
                await db.find_one({"_id": youtuber["id"]})  #  type: ignore
            ) or {"guilds": []}

            channel_db["guilds"].append(channel.guild.id)
            await db.update_one(
                {"_id": youtuber["id"]}, {"$set": channel_db}, upsert=True
            )  #  type: ignore

        except Exception as e:
            await interaction.followup.edit_message(
                interaction.message.id,  #  type: ignore
                content="error",
                view=None,
                embed=None,
            )
            if isinstance(e, ClientResponseError):
                raise PubSubHubbubResponseError(
                    e.request_info,
                    e.history,
                    status=e.status,
                    message=e.message,
                    headers=e.headers,
                ) from None

            raise

        msg = self.ctx.format_message(
            "added", {"youtuber": youtuber["title"], "channel": channel.mention}
        )
        await interaction.followup.edit_message(
            interaction.message.id,  #  type: ignore
            content=msg,
            embed=None,  #  type: ignore
            view=None,  # type: ignore
        )


class AddChannelModal(ui.Modal):
    BASE_LINK = "https://www.googleapis.com/youtube/v3"
    id_or_url_or_username = ui.TextInput(label="Channel", custom_id="channel")

    def __init__(self, ctx: StrapContext) -> None:
        super().__init__(title="placeholder")
        self.ctx = ctx

    def create_link(self, type: SearchType, query: str) -> str:
        id = type == SearchType.id
        type = SearchType.channels if id else type
        keys = {
            SearchType.search: "q",
            SearchType.channels: "id" if id else "forUsername",
        }
        # NOTE: id will be ignored if endpoint is "search"
        args = {
            "key": os.getenv("GOOGLE_API_KEY"),
            "part": "snippet",
            "maxResults": "15",
            keys[type]: query,
        }
        if type == SearchType.search:
            args["type"] = "channel"

        return f"{self.BASE_LINK}/{type.name}?{urlencode(args)}"

    def _channel_check(self, item: dict):
        kind = item["kind"]
        if kind == "youtube#searchResult":
            kind = item["id"]["kind"]

        return kind == "youtube#channel"

    async def do_search_channels(
        self, query: str, *, type: SearchType = SearchType.channels
    ) -> typing.List[dict]:
        query = query.strip()
        db = self.ctx.bot.get_db("Cache", cog=False)

        cache = await db.find_one({"query": query}) or {}  # type: ignore
        link = self.create_link(type, query)
        ret = []

        def _filter(body):
            i = []
            for item in filter(self._channel_check, body["items"]):
                if item["kind"] == "youtube#searchResult":
                    item["kind"] = item["id"]["kind"]
                    item["id"] = item["id"]["channelId"]

                i.append(item)

            return i

        used_at = cache.get("used_at", datetime.utcnow() - timedelta(hours=13))
        if datetime.utcnow() < used_at + timedelta(hours=12) and _filter(
            cache.get("body", {})
        ):
            # if less than 12 hours have passed since last time
            # and there are results in the cached data, then it
            # is useless to make another request, because data
            # is most likely the same. also, YouTube APIs are
            # very slow most of times.
            return _filter(cache["body"])

        headers = {"If-None-Match": cache.get("body", {}).get("etag", "")}

        async with self.ctx.bot.session.get(link, headers=headers) as response:
            if response.status == 304:
                await db.update_one({"query": query}, {"$set": {"used_at": datetime.utcnow()}})  # type: ignore
                ret = _filter(cache["body"])
            else:
                body = await response.json()
                page_info = body.pop("pageInfo", {})
                body["items"] = body.get("items", [])

                await db.update_one({"query": query}, {"$set": {"used_at": datetime.utcnow(), "body": body}}, upsert=True)  # type: ignore

                if page_info.get("totalResults", None):
                    ret = _filter(body)

        return ret

    async def search_channels(self, query: str) -> typing.List[dict]:
        ret = []
        for name, type in SearchType.__members__.items():
            ret = await self.do_search_channels(query, type=type)  # type: ignore
            if ret:
                break

        return ret

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()
        results = await self.search_channels(self.id_or_url_or_username.value)
        if not results:
            await interaction.followup.send(
                "no_results"
            )
            return


        await interaction.followup.send(
            f"{len(results)}\n{self.id_or_url_or_username}\n{results[0]['id']}"
        )

        paginator = ChannelsPaginator(results)
        await paginator.start(self.ctx)


class YouTubeView(View):
    def __init__(
        self,
        ctx: StrapContext,
        content: str,
        format: dict = {},
        *,
        timeout: Optional[float] = 180,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.__content = content
        self.format = format

    @property
    def content(self):
        return self.ctx.format_message(self.__content, self.format)

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        return (
            interaction.user.id == self.ctx.author.id
            and await self.ctx.bot.check_youtube_news()
        )

    @ui.button(label="btn_add")
    async def add_channel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(AddChannelModal(self.ctx))

    @ui.button(label="btn_list")
    async def list_channels(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("placeholder")

    @ui.button(label="btn_del")
    async def del_channel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("placeholder")
