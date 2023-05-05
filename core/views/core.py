import typing
from strapbot import StrapBot
from typing import Any, Optional
from discord import ui
from discord.interactions import Interaction
from discord.ui.item import Item
from ..context import StrapContext


class View(ui.View):
    def __init__(
        self, ctx: Optional[StrapContext] = None, *, timeout: Optional[float] = 180
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        if ctx:
            self.format_items()

    def format_items(self):
        assert self.ctx != None, "ctx must not be None"
        for child in self.children:
            if hasattr(child, "label"):
                child.label = self.ctx.format_message(child.label)  # type: ignore

    async def on_error(
        self, interaction: Interaction[StrapBot], error: Exception, item: Item[Any]
    ):
        custom_id = getattr(item, "custom_id", "")
        await interaction.client.handle_errors(
            error, custom_id, type(item).__name__.lower()
        )
        await super().on_error(interaction, error, item)

    async def interaction_check(self, interaction: Interaction[StrapBot]) -> bool:
        if self.ctx:
            author_id = self.ctx.author.id
        else:
            # if ctx == None this check is practically
            # useless, but at least the view still works
            author_id = interaction.user.id

        return interaction.user.id == author_id
