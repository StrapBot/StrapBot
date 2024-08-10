from .core import View
from discord import ui
from discord import Interaction, ButtonStyle
from asyncio import Event
from ..utils import MarkovChain, save_chain_to_db, MarkovChain
from motor.core import AgnosticCollection
from motor.motor_asyncio import AsyncIOMotorGridFSBucket


class MarkovChannelSetupView(View):
    def __init__(self, ctx, db, lang: dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.lang = lang
        self.db: AgnosticCollection = db

    @ui.button(label="Yes", style=ButtonStyle.green)
    async def yes(self, interaction: Interaction, button: ui.Button):
        ev = self.ctx.bot.markov_learn_events[self.ctx.guild.id] = Event()
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
        # save an empty chain to the database
        await save_chain_to_db(self.ctx.bot.mongodb, self.ctx.guild.id, MarkovChain())
        await interaction.response.edit_message(
            content=self.ctx.format_message("cancelled", lang=self.lang), view=None
        )

        self.stop()
