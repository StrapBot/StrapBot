from .core import View
from discord import (
    ui,
    Interaction,
    Embed,
    SelectOption,
    ButtonStyle,
    InteractionResponded,
)
from ..context import StrapContext
from typing import Optional, Union
from .pagination import PaginationView
from ..utils import ReviewStatus


class CustomExtensionConfirmationView(View):
    def __init__(
        self,
        ctx: StrapContext,
        url: Union[str, dict],
        name: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(ctx, *args, timeout=None, **kwargs)
        self.url = url
        self.name = name
        self.ctx: StrapContext

    @ui.button(label="btn_yes", style=ButtonStyle.green, disabled=True)
    async def yes(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.ctx.bot.send_ext_for_review(self.ctx.guild.id, self.url, self.name)  # type: ignore
        await interaction.followup.edit_message(
            interaction.message.id, content=self.ctx.format_message("done"), view=None  # type: ignore
        )
        self.stop()

    @ui.button(label="btn_no", style=ButtonStyle.red, disabled=True)
    async def no(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=self.ctx.format_message("cancelled"), view=None
        )
        self.stop()

    async def reenable_buttons(self, msg):
        for child in self.children:
            if isinstance(child, ui.Button):
                child.disabled = False

        await msg.edit(view=self)


class DenyReasonSelect(ui.Select):
    def __init__(self, ctx: StrapContext, *args, **kwargs):
        options = [
            SelectOption(
                label=" ".join(o.name.split("_")).title(),
                value=str(o.value),
            )
            for o in ReviewStatus
            if o.value < 0
        ]

        super().__init__(*args, options=options, **kwargs)
        self.ctx = ctx
        self.view: ExtensionReviewsView

    async def callback(self, interaction: Interaction):
        await self.ctx.bot.set_ext_status(
            self.view.requests[self.view.current]["_id"],  # type: ignore
            ReviewStatus(int(self.values[0])),
        )
        await self.view.remove_page(interaction, self.view.current)
        await interaction.followup.send(
            self.ctx.format_message("denied"), ephemeral=True
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        return self.ctx.author.id == interaction.user.id


class ExtensionReviewsView(PaginationView):
    def __init__(self, ctx: StrapContext, *requests: list[dict], **kwargs):
        self.requests = list(requests)
        pages = []
        for req in requests:

            desc = f"URL: {req['url']}\nName: `{req['name']}`"  # type: ignore

            guild = ctx.bot.get_guild(req["_id"])  # type: ignore
            name = str(req["_id"])  # type: ignore
            icon = None
            if guild:
                name = guild.name
                if guild.icon:
                    icon = guild.icon.url

            pages.append(
                Embed(
                    description=desc,
                ).set_author(
                    name=name,
                    icon_url=icon,
                )
            )

        self.ignore.__discord_ui_model_kwargs__["row"] = 3 + int(len(pages) > 1)  # type: ignore
        super().__init__(*pages, context=ctx, **kwargs)
        self.ctx: StrapContext
        self.add_item(
            DenyReasonSelect(
                ctx,
                placeholder="sel_deny_reason",
                custom_id="deny_reason",
            )
        )

    async def remove_page(self, interaction: Interaction, index: int):
        if len(self.pages) == 1:
            a = dict(content=self.ctx.format_message("done"), view=None, embed=None)  # type: ignore
            try:
                await interaction.response.edit_message(**a)  # type: ignore
            except InteractionResponded:
                await interaction.followup.edit_message(self.message.id, **a)  # type: ignore

            self.stop()
            return
        elif len(self.pages) == 2:
            self.remove_item(self.ignore)
            self.ignore.row = 3
            self.add_item(self.ignore)

        self.requests.pop(index)
        await super().remove_page(interaction, index)

    @ui.button(label="btn_accept", row=3, style=ButtonStyle.green)
    async def accept(self, interaction: Interaction, button: ui.Button):
        t = None
        guild_id = self.requests[self.current]["_id"]  # type: ignore
        try:
            t = self.ctx.bot.loop.create_task(self.ctx.bot.approve_review(guild_id))

            await self.remove_page(interaction, self.current)

            await interaction.followup.send(
                self.ctx.format_message("approved"),
                ephemeral=True,
            )
        finally:
            if t and not t.done():
                await t

    @ui.button(label="btn_ignore", row=4, style=ButtonStyle.blurple)
    async def ignore(self, interaction: Interaction, button: ui.Button):
        await self.remove_page(interaction, self.current)
