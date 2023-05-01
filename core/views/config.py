import os
import discord
from discord import ui
from ..config import AnyConfig, SelectMenuType, MenuType
from ..utils import get_lang_config_names, DEFAULT_LANG_ENV
from ..context import StrapContext
from typing import Optional, Union, Type, Any, Dict, List
from discord import ButtonStyle, Emoji, PartialEmoji, SelectOption

BACK_BUTTON_PROPS = dict(style=ButtonStyle.primary, emoji="⬅️", custom_id="back", row=0)
CONFIG_TEMPLATE = "**__{name}__**\n\n*{description}*"


def _get_lang_props(lang: str, key: Any):
    _ = lambda: get_lang_config_names(os.getenv(DEFAULT_LANG_ENV, "en"))
    props = get_lang_config_names(lang)
    if not props:
        props = _()

    if key not in props:
        props = _()
        if key not in props:
            return {"name": key, "description": f"Properties for `{key}` not found."}

    return props[key]  # type: ignore


class ConfigView(ui.View):
    def __init__(self, ctx: StrapContext, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        return interaction.user.id == self.ctx.author.id


class PropertyView(ConfigView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        timeout: float = 180,
    ):
        super().__init__(ctx, timeout=timeout)
        self.parent = parent
        self.config = config
        self.value = config[key]
        self.key = key

    async def set(self, value: Any):
        original_value = self.config[self.key]
        ret = await self.config.set(**{self.key: value})
        try:
            await self.config.types[self.key].setup(self.ctx, value)
        except Exception:
            await self.config.set(**{self.key: original_value})
            raise

        return ret

    @ui.button(**BACK_BUTTON_PROPS)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        if not self.parent:
            return

        for child in self.parent.children:
            if not isinstance(child, ConfigButton):
                continue

            data = _get_lang_props(self.ctx.language_to_use, child.key)

            child.label = data["name"]

        content = self.ctx.format_message(self.parent.content)
        await interaction.response.edit_message(content=content, view=self.parent)


class BooleanPropertyView(PropertyView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        timeout: float = 180,
    ):
        super().__init__(ctx, config, key, parent, timeout=timeout)
        self.update_button_name()

    def update_button_name(self):
        self.toggler.label = self.ctx.format_message(
            "bool_" + ("disable" if self.value else "enable")
        )

    @ui.button(label="Toggle", custom_id="toggle", style=ButtonStyle.green)
    async def toggler(self, interaction: discord.Interaction, button: ui.Button):
        self.value = not self.value
        await interaction.response.defer()
        await self.set(self.value)
        await self.ctx.config.fetch()
        await self.ctx.guild_config.fetch()
        data = _get_lang_props(self.ctx.language_to_use, self.key)
        cont = CONFIG_TEMPLATE.format(
            name=data["name"], description=data["description"]
        )
        self.update_button_name()
        await interaction.followup.edit_message(interaction.message.id, content=cont, view=self)  # type: ignore


# please give me a better way to do this
class ChannelSelectMenu(ui.ChannelSelect):
    async def callback(self, interaction: discord.Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class RoleSelectMenu(ui.RoleSelect):
    async def callback(self, interaction: discord.Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class UserSelectMenu(ui.UserSelect):
    async def callback(self, interaction: discord.Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class MentionableSelectMenu(ui.MentionableSelect):
    async def callback(self, interaction: discord.Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class StringSelectMenu(ui.Select):
    async def callback(self, interaction: discord.Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class SelectPropertyView(PropertyView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        options: Optional[List[SelectOption]] = None,
        timeout: float = 180,
    ):
        super().__init__(ctx, config, key, parent, timeout=timeout)
        self.config = config
        self.key = key
        self.ctx = ctx
        self.menu_type = tp = config.types[key].select_menu_type
        self.remove_item(self.back)
        self.back.row = 1
        if tp:
            kws: Dict[str, Any] = {
                "min_values": tp.min_values,
                "max_values": tp.max_values,
                "custom_id": "select",
            }

            if tp.type == MenuType.channel:
                menu = ChannelSelectMenu
                kws["channel_types"] = tp.channel_types
            elif tp.type == MenuType.user:
                menu = UserSelectMenu
            elif tp.type == MenuType.role:
                menu = RoleSelectMenu
            elif tp.type == MenuType.mentionable:
                menu = MentionableSelectMenu
            else:
                menu = StringSelectMenu
                if not options:
                    raise ValueError("options is required when MenuType is string")

                for opt in options:
                    opt.default = opt.value == config[key]
                kws["options"] = options

            self.add_item(menu(**kws))

        self.add_item(self.back)

    async def callback(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer()
        if not self.menu_type:
            await self.back.callback(interaction)
            return

        val = select.values
        if self.menu_type.type in [
            MenuType.channel,
            MenuType.user,
            MenuType.role,
            MenuType.mentionable,
        ]:
            val = [v.id for v in val]  # type: ignore

        if self.menu_type.min_values == 1 and self.menu_type.max_values == 1:
            val = val[0]

        try:
            await self.set(val)
        except Exception:
            select.disabled = True
            await interaction.followup.edit_message(
                interaction.message.id, view=self  #  type: ignore
            )
            raise
        await self.ctx.config.fetch()
        await self.ctx.guild_config.fetch()
        lang = _get_lang_props(self.ctx.language_to_use, self.key)
        cont = CONFIG_TEMPLATE.format(
            name=lang["name"], description=lang["description"]
        )

        currs = self.get_current_configs(
            self.menu_type, self.ctx, self.config[self.key]
        )
        if currs:
            if len(currs) == 1:
                curr = currs[0]
            else:
                curr = "\n- " + ("\n- ".join(currs))

            m = self.ctx.format_message("current_conf", {"current": curr})
            cont += f"\n\n{m}"

        if self.menu_type.type == MenuType.string:
            items: ui.Select = discord.utils.get(
                self.children, custom_id="select"  #  type: ignore
            )
            for opt in items.options:
                opt.default = opt.value == self.config[self.key]

        await interaction.followup.edit_message(
            interaction.message.id, content=cont, view=self  # type: ignore
        )

    @staticmethod
    def get_current_configs(menu_type: SelectMenuType, ctx: StrapContext, current):
        ret = []
        # MenuType.mentionable is to be implemented yet
        if (
            menu_type.type in [MenuType.channel, MenuType.user, MenuType.role]
            and ctx.guild
        ):
            cnf = current
            if menu_type.max_values == 1 and menu_type.min_values == 1:
                cnf = [current]

            _type = menu_type.type.name
            attr_from = ctx.bot
            if menu_type.type == MenuType.role:
                attr_from = ctx.guild

            func = getattr(attr_from, f"get_{_type}")
            ret = [m.mention for m in [func(id) for id in cnf] if m != None]

        return ret


class ConfigButton(ui.Button):
    def __init__(self, ctx: StrapContext, config: AnyConfig, key: str):
        self.data = _get_lang_props(ctx.language_to_use, key)
        super().__init__(
            style=ButtonStyle.green,
            label=self.data["name"],
            custom_id=key,
            emoji=config.emojis[key] or None,
        )
        self.config = config
        self.key = key
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.config.fetch()
        await self.ctx.guild_config.fetch()
        self.data = _get_lang_props(self.ctx.language_to_use, self.key)
        kwargs = {}
        viewtype: Type[PropertyView] = PropertyView
        content = CONFIG_TEMPLATE.format(
            name=self.data["name"], description=self.data["description"]
        )
        current = ""
        conf = self.config[self.key]
        conf_tp = self.config.types[self.key]
        if isinstance(conf, bool):
            viewtype = BooleanPropertyView
        elif conf_tp.custom:
            pass  # Modals are to be implemented yet
        elif conf_tp.select_menu_type != None:
            menu_type = conf_tp.select_menu_type
            viewtype = SelectPropertyView
            currents = viewtype.get_current_configs(menu_type, self.ctx, conf)
            if menu_type.type == MenuType.string:
                kwargs["options"] = await conf_tp.get_select_menu_values(self.ctx)

            if len(currents) == 1:
                current = currents[0]
            elif currents:
                current = "\n- " + ("\n- ".join(currents))

        if current:
            m = self.ctx.format_message("current_conf", {"current": current})
            content += f"\n\n{m}"

        view = viewtype(self.ctx, self.config, self.key, self.view, **kwargs)
        await interaction.followup.edit_message(
            interaction.message.id, content=content, view=view  #  type: ignore
        )


class ConfigMenuView(ConfigView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        parent=None,
        **kwargs,
    ):
        super().__init__(ctx, **kwargs)
        self.config = config
        self.content = "choose_config"

        self.parent = parent
        if not parent:
            self.remove_item(self.back)

        for k in self.config.data.keys():
            button = ConfigButton(ctx, config, k)
            self.add_item(button)

    @ui.button(**BACK_BUTTON_PROPS)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        if not self.parent:
            return

        content = self.ctx.format_message(self.parent.content)
        for child in self.parent.children:
            child.label = self.ctx.format_message(child.label_to_format)

        await interaction.response.edit_message(content=content, view=self.parent)


class ModChoiceButton(ui.Button):
    def __init__(
        self,
        ctx: StrapContext,
        *,
        style: ButtonStyle = ButtonStyle.blurple,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[Union[str, Emoji, PartialEmoji]] = None,
        row: Optional[int] = None,
    ):
        self.label_to_format = f"{custom_id}_button_label"
        super().__init__(
            style=style,
            label=ctx.format_message(self.label_to_format),
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )
        self.ctx = ctx
        self.bot = ctx.bot
        self.view: ModChoiceView

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = await self.bot.get_config(getattr(self.view, str(self.custom_id)))
        view = ConfigMenuView(self.ctx, cfg, self.view)  #  type: ignore
        await interaction.followup.edit_message(
            interaction.message.id,  # type: ignore
            content=self.ctx.format_message(view.content),
            view=view,
        )


class ModChoiceView(ConfigView):
    def __init__(self, ctx: StrapContext, *, timeout: float = 180.0):
        super().__init__(ctx, timeout=timeout)
        self.user = ctx.author
        self.guild = ctx.guild
        self.bot = ctx.bot
        self.content = "mod_choice"
        self.add_item(ModChoiceButton(ctx, custom_id="guild"))
        self.add_item(ModChoiceButton(ctx, custom_id="user"))
