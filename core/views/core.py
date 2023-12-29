import typing

from discord.utils import MISSING
from strapbot import StrapBot
from typing import Any, Dict, List, Optional
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
        if self.ctx == None:
            raise TypeError("ctx must not be None")

        if isinstance(self, Modal):
            children = self.__modal_children_items__.values()
        else:
            children = self.children

        if getattr(self, "title", MISSING) is not MISSING:
            self.title = self.ctx.format_message(self.title)

        for child in children:
            if hasattr(child, "label") and child.label != None:
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
            # at this point this check is practically
            # useless, but at least the view still works
            author_id = interaction.user.id

        return interaction.user.id == author_id


class Modal(ui.Modal, View):
    def __init__(
        self,
        ctx: Optional[StrapContext] = None,
        *,
        title: str = MISSING,
        timeout: Optional[float] = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        View.__init__(self, ctx, timeout=timeout)

    def to_components(self) -> List[Dict[str, Any]]:
        components = super().to_components()
        if self.ctx:
            for component in components:
                for comp in component.get("components", {}):
                    comp["label"] = self.ctx.format_message(comp["label"])

        return components
