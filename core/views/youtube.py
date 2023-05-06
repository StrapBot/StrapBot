import discord
import os
import typing
from aiohttp import ClientResponse, ClientResponseError, RequestInfo
from aiohttp.typedefs import LooseHeaders
from ..context import StrapContext
from datetime import datetime, timedelta
from discord import ui, Interaction, ButtonStyle
from enum import Enum
from typing import Optional, Tuple
from urllib.parse import urlencode
from . import View, Modal, PaginationView, StopButton
from ..utils import get_guild_youtube_channels, paginate_list


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
    def __init__(
        self,
        view: "YouTubeView",
        results: list,
        used_by: typing.Literal["add", "del"] = "add",
        **kwargs,
    ):
        self.results = results
        kwargs["context"] = self.ctx = view.ctx
        self.used_by = used_by
        pages = [self.parse_result(x) for x in results]
        kwargs["stop_button"] = kwargs.pop("stop_button", None) or BackButton(view)
        super().__init__(*pages, **kwargs)
        if used_by == "del":
            self.choose.label = self.ctx.format_message("btn_delete")
            self.choose.style = discord.ButtonStyle.red

    def parse_result(self, result: dict) -> discord.Embed:
        e = {"add": "results", "del": "delete"}[self.used_by]
        ret = (
            discord.Embed(
                title=result["title"],
                description=result["description"].strip() or "missing_desc",
                color=self.ctx.me.accent_color,
                url=f"https://youtube.com/channel/{result['id']}",
            )
            .set_author(
                name=f"{e}_embed_title",
                icon_url=self.ctx.me.avatar,
            )
            .set_thumbnail(url=result["thumbnails"]["default"]["url"])
        )

        return ret

    @ui.button(custom_id="choose", label="btn_choose", style=discord.ButtonStyle.green)
    async def choose(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        subscribe = self.used_by == "add"
        youtuber = self.results[self.current]
        channel: discord.TextChannel = self.ctx.bot.get_channel(  #  type: ignore
            self.ctx.guild_config.yt_news_channel_id
        )

        try:
            db = self.ctx.bot.get_db("YouTubeNews", False)
            channel_db = (
                await db.find_one({"_id": youtuber["id"]})  #  type: ignore
            ) or {"guilds": []}

            if subscribe and channel.guild.id in channel_db["guilds"]:
                await interaction.followup.edit_message(
                    interaction.message.id,  #  type: ignore
                    content=self.ctx.format_message("already_added"),
                    view=None,
                    embed=None,
                )
                return

            f = channel_db["guilds"].append
            if not subscribe:
                f = channel_db["guilds"].remove

            f(channel.guild.id)

            # convert guilds to a set to avoid duplicates,
            # then converting it back to list
            channel_db["guilds"] = list(set(channel_db["guilds"]))
            channel_db["data"] = youtuber

            guilds_check = bool(channel_db["guilds"])
            await self.ctx.bot.request_pubsubhubbub(
                youtuber["id"], subscribe or guilds_check
            )
            await db.update_one(
                {"_id": youtuber["id"]}, {"$set": channel_db}, upsert=True
            )  #  type: ignore

        except Exception as e:
            await interaction.followup.edit_message(
                interaction.message.id,  #  type: ignore
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
            "added" if subscribe else "deleted",
            {"youtuber": youtuber["title"], "channel": channel.mention},
        )
        await interaction.followup.edit_message(
            interaction.message.id,  #  type: ignore
            content=msg,
            embed=None,  #  type: ignore
            view=None,  # type: ignore
        )


class AddChannelModal(Modal):
    BASE_LINK = "https://www.googleapis.com/youtube/v3"
    id_or_url_or_username = ui.TextInput(
        label="channel_input_label", custom_id="channel"
    )

    def __init__(self, view: "YouTubeView") -> None:
        super().__init__(view.ctx, title="add_modal_title")
        self.view = view
        self.ctx = view.ctx

    def create_link(self, type: SearchType, query: str) -> str:
        id = type == SearchType.id
        type = SearchType.channels if id else type
        keys = {
            SearchType.search: "q",
            SearchType.channels: "id" if id else "forUsername",
        }
        args = {
            "key": os.getenv("GOOGLE_API_KEY"),
            "part": "snippet",
            "maxResults": "15",
            keys[type]: query,
        }
        if type == SearchType.search:
            args["type"] = "channel"

        return f"{self.BASE_LINK}/{type.name}?{urlencode(args)}"

    @staticmethod
    def _channel_check(item: dict):
        kind = item["kind"]
        if kind == "youtube#searchResult":
            kind = item["id"]["kind"]

        return kind == "youtube#channel"

    @classmethod
    def simplify_results(cls, body):
        i = []
        for item in filter(cls._channel_check, body["items"]):
            if item["kind"] == "youtube#searchResult":
                item["kind"] = item["id"]["kind"]
                item["id"] = item["id"]["channelId"]

            if "snippet" in item:
                item.update(item["snippet"])
                del item["snippet"]

            i.append(item)

        return i

    async def do_search_channels(
        self, query: str, *, type: SearchType = SearchType.channels
    ) -> typing.List[dict]:
        query = query.strip()
        db = self.ctx.bot.get_db("Cache", cog=False)

        cache = await db.find_one({"query": query}) or {}  # type: ignore
        link = self.create_link(type, query)
        ret = []

        used_at = cache.get("used_at", datetime.utcnow() - timedelta(hours=13))
        if datetime.utcnow() < used_at + timedelta(hours=12) and self.simplify_results(
            cache.get("body", {})
        ):
            # if less than 12 hours have passed since last time
            # and there are results in the cached data, then it
            # is useless to make another request, because data
            # is most likely the same. also, YouTube APIs are
            # very slow most of times.
            return self.simplify_results(cache["body"])

        headers = {"If-None-Match": cache.get("body", {}).get("etag", "")}

        async with self.ctx.bot.session.get(link, headers=headers) as response:
            if response.status == 304:
                await db.update_one({"query": query}, {"$set": {"used_at": datetime.utcnow()}})  # type: ignore
                ret = self.simplify_results(cache["body"])
            else:
                body = await response.json()
                page_info = body.pop("pageInfo", {})
                body["items"] = body.get("items", [])

                await db.update_one({"query": query}, {"$set": {"used_at": datetime.utcnow(), "body": body}}, upsert=True)  # type: ignore

                if page_info.get("totalResults", None):
                    ret = self.simplify_results(body)

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
        # TODO: add loading
        results = await self.search_channels(self.id_or_url_or_username.value)
        if not results:
            await interaction.followup.send("no_results")
            return

        paginator = ChannelsPaginator(self.view, results)
        kwargs = await paginator.setup(interaction.user)
        await interaction.followup.edit_message(interaction.message.id, **kwargs)  # type: ignore


class YouTubeView(View):
    def __init__(
        self,
        ctx: StrapContext,
        content: str,
        format: dict = {},
        *,
        timeout: Optional[float] = 180,
    ):
        super().__init__(ctx, timeout=timeout)
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

    @ui.button(label="btn_add", style=ButtonStyle.primary)
    async def add_channel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(AddChannelModal(self))

    @ui.button(label="btn_list", style=ButtonStyle.primary)
    async def list_channels(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        chdb = self.ctx.bot.get_db("YouTubeNews", False)
        gddb = self.ctx.bot.get_db("YouTubeNewsGuilds", False)
        channels = await chdb.find().to_list(None)
        guild_data = await gddb.find_one({"_id": interaction.guild_id})  # type: ignore
        data = get_guild_youtube_channels(channels, guild_data)
        if not data["channels"]:
            await interaction.followup.edit_message(
                interaction.message.id,  # type: ignore
                content=self.ctx.format_message("channels_empty"),
                embed=None,
                view=None,
            )
            return

        pages = []
        items_per_page = 10
        for j, chns in enumerate(paginate_list(data["channels"], items_per_page)):
            desc = []
            for i, chn in enumerate(chns):
                title = chn["title"]
                if len(title) > 30:
                    title = title[:27] + "..."

                url = f"https://youtube.com/channel/{chn['id']}"

                jj = items_per_page * j
                title = f"{jj+i+1}. [**`{title}`**]({url})"
                desc.append(title)

            pages.append(
                discord.Embed(
                    description="\n".join(desc), color=self.ctx.me.accent_color
                ).set_author(name="channels_list", icon_url=self.ctx.me.avatar)
            )

        view = PaginationView(*pages, context=self.ctx, stop_button=BackButton(self))
        kwargs = await view.setup(interaction.user)
        await interaction.followup.edit_message(
            interaction.message.id, **kwargs  #  type: ignore
        )

    @ui.button(label="btn_del", style=ButtonStyle.primary)
    async def del_channel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        chdb = self.ctx.bot.get_db("YouTubeNews", False)
        gddb = self.ctx.bot.get_db("YouTubeNewsGuilds", False)
        channels = await chdb.find().to_list(None)
        guild_data = await gddb.find_one({"_id": interaction.guild_id})  # type: ignore
        data = get_guild_youtube_channels(channels, guild_data)["channels"]
        if not data:
            await interaction.followup.edit_message(
                interaction.message.id,  # type: ignore
                content=self.ctx.format_message("channels_empty"),
                embed=None,
                view=None,
            )
            return

        paginator = ChannelsPaginator(self, data, "del")
        kwargs = await paginator.setup(interaction.user)
        await interaction.followup.edit_message(interaction.message.id, **kwargs)  # type: ignore
