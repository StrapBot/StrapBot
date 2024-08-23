from .core import View
from discord import ui, Interaction, Embed, SelectOption, ButtonStyle
from ..context import StrapContext
from typing import Optional
from .pagination import PaginationView
from ..utils import ReviewStatus


class CustomExtensionConfirmationView(View):
    def __init__(
        self, ctx: StrapContext, url: str, name: Optional[str] = None, *args, **kwargs
    ):
        super().__init__(ctx, *args, timeout=None, **kwargs)
        self.url = url
        self.name = name

    @ui.button(label="btn_yes", style=ButtonStyle.green, disabled=True)
    async def yes(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.ctx.bot.send_ext_for_review(self.ctx.guild.id, self.url, self.name)
        await interaction.followup.edit_message(interaction.message.id, content="done", view=None)
        self.stop()

    @ui.button(label="btn_no", style=ButtonStyle.red, disabled=True)
    async def no(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="cancelled", view=None)
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
                label=" ".join(o.name.split("_")).capitalize(),
                value=o.value,
            )
            for o in ReviewStatus
        ]

        super().__init__(*args, options=options, **kwargs)
        self.ctx = ctx
        self.view: ExtensionReviewsView

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.ctx.bot.set_ext_status(
            self.view.requests[self.view.current]["_id"],
            ReviewStatus(int(self.values[0])),
        )
        await interaction.response.send_message("Success", ephemeral=True)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return self.ctx.author.id == interaction.user.id


class AcceptButton(ui.Button):
    def __init__(self, ctx: StrapContext, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = ctx
        self.view: ExtensionReviewsView

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        t = None
        try:
            t = self.ctx.bot.loop.create_task(
                self.ctx.bot.approve_review(
                    self.view.requests[self.view.current]["_id"]
                )
            )

            await interaction.response.send_message(
                "Success, the extension is " "being set up in the background",
                ephemeral=True,
            )
        finally:
            if t and not t.done():
                await t

    async def interaction_check(self, interaction: Interaction) -> bool:
        return self.ctx.author.id == interaction.user.id


class ExtensionReviewsView(PaginationView):
    def __init__(self, ctx: StrapContext, *requests: list[dict], **kwargs):
        self.ctx = ctx
        self.requests = requests
        pages = []
        for req in requests:
            
            desc = f"URL: {req['url']}\nName: `{req['name']}`"

            guild = ctx.bot.get_guild(req["_id"])
            name = str(req["_id"])
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

        super().__init__(*pages, **kwargs)
        self.add_item(
            DenyReasonSelect(
                ctx, placeholder="Deny? Select a reason here", custom_id="deny_reason"
            )
        )
        self.add_item(AcceptButton(ctx, label="Accept", style=ButtonStyle.green))
