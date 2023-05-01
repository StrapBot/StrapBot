import discord
from typing import List, Union
from typing_extensions import Self
from discord import Embed, ButtonStyle
from discord import ui
from . import View
from core.context import StrapContext

# subclass this when making a custom stop button
class StopButton(ui.Button):
    def __init__(self, emoji: str = "⏹️"):
        super().__init__(
            emoji=emoji or "⏹️", custom_id="nav_stop", style=ButtonStyle.blurple
        )
        self.view: PaginationView

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        self.view.stop()  # type: ignore


class PaginationView(View):
    def __init__(self, *pages: Union[Embed, List[Embed], str], **kwargs):
        stop_button: StopButton = kwargs.pop("stop_button", None) or StopButton()
        self.current = kwargs.pop("index", 0)
        super().__init__(**kwargs)
        stop_button._view = self
        if not isinstance(stop_button, StopButton):
            raise ValueError("custom stop buttons must derive from StopButton")

        self._stop_button_changed = stop_button.__class__ != StopButton

        # just in case the order is changed in the future
        for i, c in enumerate(self.children):
            if c == self.stop_button:
                stop_button._row = c._row
                stop_button._rendered_row = c._rendered_row
                self._children[i] = stop_button
                break

        self.pages: List[dict] = []
        self.author: Union[discord.Member, discord.User]
        if not pages:
            raise ValueError
        for page in pages:
            if isinstance(page, Embed):
                embeds = [page]
            elif not isinstance(page, list):
                embeds = []
            else:
                embeds = list(filter(lambda a: isinstance(a, Embed), page))

            content = page if not embeds else None
            if not content and not embeds:
                continue

            self.pages.append(
                {"embeds": embeds, "content": str(content) if content else None}
            )

    @property
    def navigation_children(self) -> List[ui.Item[Self]]:
        def check(child):
            return child.custom_id.startswith("nav_")

        return list(filter(check, self.children))

    @property
    def additional_children(self):
        return [c for c in self.children if c not in self.navigation_children]

    def update_embeds(self, embeds: List[discord.Embed]) -> List[discord.Embed]:
        ret = []
        for emb in embeds:
            embed = emb.copy()
            footer = embed.footer.text
            footer_text = f"Page {self.current + 1} of {len(self.pages)}"
            footer_text += f" | {footer}" if footer else ""
            embed.set_footer(text=footer_text, icon_url=embed.footer.icon_url)
            ret.append(embed)
        return ret

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        return interaction.user.id == self.author.id

    async def on_timeout(self) -> None:
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    async def setup(
        self, author: Union[discord.Member, discord.User], **kwargs
    ) -> dict:
        """
        A manual alternative to start() to use
        for `Interaction`s or when editing a message.

        Returns the keyword arguments to pass.
        """
        self.author = author
        kwargs.update(self.pages[self.current].copy())
        if len(self.pages) > 1 or self.additional_children or self._stop_button_changed:
            kwargs["view"] = self
            if len(self.pages) > 1:
                self.update_buttons()
            else:
                for i in self.navigation_children:
                    if isinstance(i, StopButton) and self._stop_button_changed:
                        # the stop button has been replaced, don't remove it
                        continue

                    self.remove_item(i)

        elif "view" not in kwargs:
            kwargs["view"] = None

        if kwargs["embeds"]:
            kwargs["embeds"] = self.update_embeds(kwargs["embeds"])

        return kwargs

    async def start(self, ctx: StrapContext, reply="", **kwargs):
        kwargs.update(await self.setup(ctx.author, **kwargs))

        if reply == None:
            send = ctx.send
        elif isinstance(reply, discord.Message):
            send = reply.reply
        else:
            send = ctx.reply

        self.message = await send(**kwargs)
        return self.message

    async def show_page(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.author.id:
            return
        if index > len(self.pages) - 1:
            raise IndexError
        self.current = index
        self.update_buttons()
        kwargs = self.pages[index].copy()
        kwargs["view"] = self
        if kwargs["embeds"]:
            kwargs["embeds"] = self.update_embeds(kwargs["embeds"])

        await interaction.response.edit_message(**kwargs)

    def update_buttons(self):
        l_disabled = self.current == 0
        r_disabled = self.current == len(self.pages) - 1
        self.first_page.disabled = l_disabled
        self.previous_page.disabled = l_disabled
        self.next_page.disabled = r_disabled
        self.last_page.disabled = r_disabled

    @ui.button(emoji="◀️", custom_id="nav_previous", row=3, style=ButtonStyle.green)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        curr = self.current
        if curr <= 0:
            curr = 1
        await self.show_page(interaction, curr - 1)

    @ui.button(custom_id="nav_stop", row=3)
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        ...

    @ui.button(emoji="▶️", custom_id="nav_next", row=3, style=ButtonStyle.green)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        curr = self.current
        if curr >= len(self.pages):
            curr = len(self.pages) - 2

        await self.show_page(interaction, curr + 1)

    @ui.button(emoji="⏮️", custom_id="nav_first", row=4, style=ButtonStyle.green)
    async def first_page(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_page(interaction, 0)

    @ui.button(emoji="🔢", custom_id="nav_num", row=4, style=ButtonStyle.blurple)
    async def choose_page(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.author.id:
            return

        await interaction.response.send_modal(PageModal(self))

    @ui.button(emoji="⏭️", custom_id="nav_last", row=4, style=ButtonStyle.green)
    async def last_page(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_page(interaction, len(self.pages) - 1)


class PageModal(ui.Modal, title="Jump to page..."):
    page = ui.TextInput(
        label="Which page do you want to jump to?",
        style=discord.TextStyle.short,
        placeholder="Insert the page here...",
    )

    def __init__(self, paginator: PaginationView, **kwargs):
        super().__init__(**kwargs)
        self.paginator = paginator

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page.value)
        except Exception:
            await interaction.response.send_message(
                "The page must be a number.", ephemeral=True
            )
            return

        if page <= 0 or page > len(self.paginator.pages):
            await interaction.response.send_message(
                "The page number must be between 1" f"and {len(self.paginator.pages)}",
                ephemeral=True,
            )

        await self.paginator.show_page(interaction, int(self.page.value) - 1)
