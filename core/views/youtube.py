import os
import discord
import typing
from enum import Enum
from discord import Interaction
from ..context import StrapContext
from discord import ui
from typing import Optional
from urllib.parse import quote as urlencode


class SearchType(Enum):
    id = -1
    username = 0
    search = 1


class AddChannelModal(ui.Modal):
    id_or_url_or_username = ui.TextInput(label="Channel", custom_id="channel")
    BASE_LINK = "https://www.googleapis.com/youtube/v3"
    CHANNELS_LINK = (
        f"{BASE_LINK}/channels?part=snippet&key={os.getenv('GOOGLE_API_KEY')}"
    )
    SEARCH_LINK = f"{BASE_LINK}/search?key={os.getenv('GOOGLE_API_KEY')}"
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

    async def search_channels(
        self, query: str, *, type: SearchType = SearchType.username
    ) -> typing.List[dict]:
        query = query.strip()
        db = self.ctx.bot.get_db("Cache", cog=False)

        # TODO: check if use search or username or id
        cache = await db.find_one({"query": query}) or {}  # type: ignore
        link = f"{self.LINKS[type]}&{self.ARG_TYPES[type]}={urlencode(query)}"
        ret = []

        headers = {"If-None-Match": cache.get("body", {}).get("etag", "")}

        def _filter(body):
            i = []
            for item in filter(self._channel_check, body["items"]):
                if item["kind"] == "youtube#searchResult":
                    item["kind"] = item["id"]["kind"]
                    item["id"] = item["id"]["channelId"]

                i.append(item)

            return i

        async with self.ctx.bot.session.get(link, headers=headers) as response:
            from datetime import datetime

            if response.status == 304:
                used_at = datetime.utcnow()
                await db.update_one({"query": query}, {"$set": {"used_at": used_at}})  # type: ignore
                ret = _filter(cache["body"])
            else:
                body = await response.json()
                page_info = body.pop("pageInfo", {})
                body["items"] = body.get("items", [])

                await db.update_one({"query": query}, {"$set": {"used_at": datetime.utcnow(), "body": body}}, upsert=True)  # type: ignore

                if page_info.get("totalResults", None):
                    ret = _filter(body)

        return ret

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()
        results = await self.search_channels(self.id_or_url_or_username.value)
        if not results:
            await interaction.followup.send(
                f"trying id on query={self.id_or_url_or_username.value!r}"
            )
            results = await self.search_channels(
                self.id_or_url_or_username.value, type=SearchType.id
            )
            if not results:
                await interaction.followup.send(
                    f"trying search on query={self.id_or_url_or_username.value!r}"
                )
                results = await self.search_channels(
                    self.id_or_url_or_username.value, type=SearchType.search
                )
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
