import typing
from strapbot import StrapBot
from typing import Any
from discord import ui
from discord.interactions import Interaction
from discord.ui.item import Item


class View(ui.View):
    async def on_error(
        self, interaction: Interaction[StrapBot], error: Exception, item: Item[Any]
    ):
        custom_id = getattr(item, "custom_id", "")
        await interaction.client.handle_errors(
            error, custom_id, type(item).__name__.lower()
        )
        await super().on_error(interaction, error, item)
