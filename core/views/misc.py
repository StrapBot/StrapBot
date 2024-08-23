from .core import View
from discord import ui
from discord import Interaction, ButtonStyle
from asyncio import Event
from typing import Optional
from ..utils import MarkovChain, save_chain_to_db, MarkovChain
from motor.core import AgnosticCollection
from ..context import StrapContext


class MarkovChannelSetupView(View):
    def __init__(self, ctx: StrapContext, db, lang: dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.lang = lang
        self.ctx: StrapContext
        self.db: AgnosticCollection = db

    @ui.button(label="Yes", style=ButtonStyle.green)
    async def yes(self, interaction: Interaction, button: ui.Button):
        if not self.ctx.guild:
            return  # let it fail - guild-only command

        ev = self.ctx.bot.markov_learn_events[self.ctx.guild.id] = Event()  # type: ignore
        try:
            await interaction.response.edit_message(
                content=self.ctx.format_message("learning", lang=self.lang), view=None
            )

            chain = MarkovChain()
            async for message in self.ctx.channel.history(limit=None):
                ctx = await self.ctx.bot.get_context(message)
                if message.author.bot or ctx.command:
                    continue

                chain.add_message(message.content)

            await save_chain_to_db(self.ctx.bot.mongodb, self.ctx.guild.id, chain)

            await self.ctx.channel.send(self.ctx.format_message("done", lang=self.lang))
        finally:
            ev.set()
            self.ctx.bot.markov_learn_events.pop(self.ctx.guild.id, None)
            self.stop()

    @ui.button(label="No", style=ButtonStyle.red)
    async def no(self, interaction: Interaction, button: ui.Button):
        if not self.ctx.guild:
            return  # read above

        # save an empty chain to the database
        await save_chain_to_db(self.ctx.bot.mongodb, self.ctx.guild.id, MarkovChain())
        await interaction.response.edit_message(
            content=self.ctx.format_message("cancelled", lang=self.lang), view=None
        )

        self.stop()


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
        await interaction.response.edit_message(content="done", view=None)
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
