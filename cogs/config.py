import os
import asyncio
import discord
import random
import json
from core import commands
from collections import Counter
from discord_slash.utils.manage_components import (
    create_button,
    create_actionrow,
    wait_for_component,
)
from discord_slash.model import ButtonStyle
from discord_slash import ComponentContext

type_ = type


class Config(commands.Cog):
    """Configure StrapBot!"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.config.db
        self.aborts = Counter()

    @commands.command(
        aliases=["settings", "cfg"],
    )
    async def config(self, ctx):
        """Configure StrapBot with your favorite settings."""
        if self.aborts[ctx.author.id] > 5:
            self.aborts[ctx.author.id] = 0
        embed = discord.Embed(color=discord.Color.red(), title=ctx.lang.error)
        close_button = create_button(
            style=ButtonStyle.red, label="Close", custom_id="close"
        )
        msg = None
        button_ctx: ComponentContext = None

        def authorcheck(cctx: ComponentContext):
            return cctx.author.id == ctx.author.id and cctx.channel.id == ctx.channel.id

        if ctx.channel.permissions_for(ctx.author).manage_guild:
            buttons = [
                create_button(
                    style=ButtonStyle.blurple,
                    label="Server config",
                    custom_id="guild",
                ),
                create_button(
                    style=ButtonStyle.blurple, label="User config", custom_id="author"
                ),
                close_button,
            ]
            action_row = create_actionrow(*buttons)

            msg = await ctx.send(
                "Which one do you want to edit?", components=[action_row]
            )

            try:
                button_ctx: ComponentContext = await wait_for_component(
                    self.bot, components=action_row, check=authorcheck, timeout=30
                )
            except asyncio.TimeoutError:
                await msg.edit(content="Aborted.", components=[])
                return
            type = button_ctx.custom_id
            if type == "close":
                await button_ctx.edit_origin(content="Aborted.", components=[])
                return
        else:
            type = "author"

        id = getattr(ctx, type).id
        base = self.bot.config.get_base(self.bot.config.get_idtype(id))
        buttons = []
        for key, _ in base.items():
            if not key in ctx.lang.keys_:
                continue

            buttons.append(
                create_button(
                    style=ButtonStyle.blurple,
                    label=ctx.lang.keys_[key],
                    custom_id=key,
                    emoji=random.choice(ctx.lang.emojis.get(key, [None])),
                )
            )
        buttons.append(close_button)
        action_row = create_actionrow(*buttons)
        if msg:
            await button_ctx.edit_origin(
                content="What do you want to edit?", components=[action_row]
            )
        else:
            msg = await ctx.send("What do you want to edit?", components=[action_row])

        try:
            button_ctx: ComponentContext = await wait_for_component(
                self.bot, components=action_row, check=authorcheck, timeout=30
            )
        except asyncio.TimeoutError:
            await msg.edit(content="Aborted.", components=[])
            return

        key = button_ctx.custom_id
        if key == "close":
            self.aborts[ctx.author.id] += 1
            m = "Aborted."
            if self.aborts[ctx.author.id] >= 5:
                m = "Abroted."
            await button_ctx.edit_origin(content=m, components=[])
            return
        buttons = []

        val = await self.bot.config.get(id, key)
        if base[key] == bool:
            val = ctx.lang.bools[str(val).lower()]
            if key == "beta":
                val = val.plural
            else:
                val = val.singular

            for b in [True, False]:
                b = str(b).lower()
                buttons.append(
                    create_button(
                        style=ButtonStyle.green,
                        label=ctx.lang.bools[b].toggle,
                        custom_id=b,
                        emoji=random.choice(ctx.lang.emojis.get(b, [None])),
                    )
                )
        elif base[key] == str:
            # TODO: add handler for more strings
            if key == "lang":
                val = ctx.lang.values_[val]
                langs = os.listdir("core/languages")
                for l in langs:
                    if (
                        json.load(open(f"core/languages/{l}")).get("hidden", False)
                        and self.aborts[ctx.author.id] < 5
                    ):
                        continue
                    l = l.replace(".json", "")
                    buttons.append(
                        create_button(
                            style=ButtonStyle.green,
                            label=ctx.lang.values_[l],
                            custom_id=l,
                            emoji=random.choice(ctx.lang.emojis.get(l, [None])),
                        )
                    )

        buttons.append(close_button)
        action_row = create_actionrow(*buttons)
        await button_ctx.edit_origin(
            content=ctx.lang.questions[key].format(val=val), components=[action_row]
        )

        try:
            button_ctx: ComponentContext = await wait_for_component(
                self.bot, components=action_row, check=authorcheck, timeout=30
            )
        except asyncio.TimeoutError:
            await msg.edit(content="Aborted.", components=[])
            return

        value = button_ctx.custom_id
        if value == "close":
            await button_ctx.edit_origin(content="Aborted.", components=[])
            return

        val = value
        if base[key] == bool:
            val = ctx.lang.bools[value].singular

        if value == "true":
            value = True
        elif value == "false":
            value = False

        embed = discord.Embed(title=ctx.lang.error, color=discord.Color.red())
        kwargs = {"components": []}
        try:
            await self.bot.config.set(id, ctx.lang.current, **{key: value})
        except Exception as exc:
            embed.description = str(exc)
            kwargs["embed"] = embed
        else:
            ctx.lang = await ctx.get_lang()
            set_ = ctx.lang.boolset if base[key] == bool else ctx.lang.set
            kwargs["content"] = set_.format(key=ctx.lang.keys_[key], value=val)

        await button_ctx.edit_origin(**kwargs)


def setup(bot):
    bot.add_cog(Config(bot))
