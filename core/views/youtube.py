import os
import discord
import typing
from ..context import StrapContext
from datetime import datetime, timedelta
from discord import Interaction
from discord import ui
from enum import Enum
from typing import Optional
from urllib.parse import quote as urlencode


class SearchType(Enum):
    username = 0
    id = -1
    search = 1


class AddChannelModal(ui.Modal):
    id_or_url_or_username = ui.TextInput(label="Channel", custom_id="channel")
    BASE_LINK = "https://www.googleapis.com/youtube/v3"
    CHANNELS_LINK = (
        f"{BASE_LINK}/channels?part=snippet&key={os.getenv('GOOGLE_API_KEY')}"
    )
    SEARCH_LINK = f"{BASE_LINK}/search?part=snippet&key={os.getenv('GOOGLE_API_KEY')}"
    ARG_TYPES = {
        SearchType.id: "id",
        SearchType.username: "forUsername",
        SearchType.search: "q",
    }
    LINKS = {
        SearchType.id: CHANNELS_LINK,
        SearchType.username: CHANNELS_LINK,
        SearchType.search: SEARCH_LINK,
    }

    def __init__(self, ctx: StrapContext) -> None:
        super().__init__(title="placeholder")
        self.ctx = ctx

    def _channel_check(self, item: dict):
        kind = item["kind"]
        if kind == "youtube#searchResult":
            kind = item["id"]["kind"]

        return kind == "youtube#channel"

    async def do_search_channels(
        self, query: str, *, type: SearchType = SearchType.username
    ) -> typing.List[dict]:
        query = query.strip()
        db = self.ctx.bot.get_db("Cache", cog=False)

        cache = await db.find_one({"query": query}) or {}  # type: ignore
        link = f"{self.LINKS[type]}&{self.ARG_TYPES[type]}={urlencode(query)}"
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
        if datetime.utcnow() < used_at + timedelta(hours=12) and cache.get(
            "body", {}
        ).get("items", []):
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
                f"no_results query={self.id_or_url_or_username.value!r}"
            )
            return

        await interaction.followup.send(
            f"{len(results)}\n{self.id_or_url_or_username}\n{results[0]['id']}"
        )


class YouTubeView(ui.View):
    def __init__(self, ctx: StrapContext, *, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.ctx = ctx

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        return (
            interaction.user.id == self.ctx.author.id
            and await self.ctx.bot.check_youtube_news()
        )

    @ui.button(label="chn_add")
    async def add_channel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(AddChannelModal(self.ctx))

    @ui.button(label="chn_list")
    async def list_channels(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("placeholder")

    @ui.button(label="chn_del")
    async def del_channel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("placeholder")
