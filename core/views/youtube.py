import os
import discord
import typing
from discord import Interaction
from ..context import StrapContext
from discord import ui
from typing import Optional
from urllib.parse import quote as urlencode


class AddChannelModal(ui.Modal):
    id_or_url_or_username = ui.TextInput(label="Channel", custom_id="channel")

    CHANNELS_LINK = f"https://www.googleapis.com/youtube/v3/channels?part=id&key={os.getenv('GOOGLE_API_KEY')}"
    SEARCH_LINK = f"https://www.googleapis.com/youtube/v3/search?key={os.getenv('GOOGLE_API_KEY')}"

    def __init__(self, ctx: StrapContext) -> None:
        super().__init__(title="placeholder")
        self.ctx = ctx

    def _channel_check(self, item: dict):
        kind = item["kind"]
        if kind == "youtube#searchResult":
            kind = item["id"]["kind"]

        return kind == "youtube#channel"

    async def search_channels(self, query: str, *, search: bool=False) -> typing.List[dict]:
        # TODO: add caching to not run out of API quotas
        link = f"{self.SEARCH_LINK}&q=" if search else f"{self.CHANNELS_LINK}&forUsername="
        link += urlencode(query)
        ret = []

        async with self.ctx.bot.session.get(link) as response:
            body = await response.json()
            for item in filter(self._channel_check, body["items"]):
                if item["kind"] == "youtube#searchResult":
                    item["kind"] = item["id"]["kind"]
                    item["id"] = item["id"]["channelId"]

                ret.append(item)

        return ret

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()
        results = await self.search_channels(self.id_or_url_or_username.value)
        if not results:
            results = await self.search_channels(self.id_or_url_or_username.value, search=True)
            if not results:
                await interaction.followup.send("no_results")
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
