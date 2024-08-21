import os
import discord
import asyncio
from discord import ui, Interaction
from . import View, Modal
from ..config import (
    AnyConfig,
    SelectMenuType,
    MenuType,
    ConfigValueError,
    FolderConfigData,
    get_lang_props,
)
from ..context import StrapContext
from typing import Optional, Union, Type, Any, Dict, List
from discord import ButtonStyle, Emoji, PartialEmoji, SelectOption

BACK_BUTTON_PROPS: dict[Any, Any] = dict(
    style=ButtonStyle.primary, emoji="⬅️", custom_id="back", row=0
)
CONFIG_TEMPLATE = "**__{name}__**\n\n*{description}*"


async def items_back(self, interaction: Interaction, button: ui.Button):
    if not self.parent or self._setting_prop:
        return

    for child in self.parent.children:
        if not isinstance(child, ConfigButton):
            continue

        data = get_lang_props(self.ctx.language_to_use, child.key, self.folder)

        child.label = data["name"]

    if hasattr(self.parent, "_set_buttons"):
        self.parent._set_buttons(self.ctx)

    content = self.ctx.format_message(self.parent.content)
    await interaction.response.edit_message(content=content, view=self.parent)


class ConfigView(View):
    def __init__(self, ctx: StrapContext, *, timeout: Optional[float] = 180):
        super().__init__(ctx, timeout=timeout)
        self.ctx = ctx  # at least Pylance doesn't complain now


class PropertyView(ConfigView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        folder: Optional[FolderConfigData] = None,
        timeout: Optional[float] = 180,
    ):
        super().__init__(ctx, timeout=timeout)
        self.parent = parent
        self.config = config

        self.folder = folder
        if folder:
            self.value = config[folder.key][key]
        else:
            self.value = config[key]

        self.key = key
        self._setting_prop = False

    async def set(self, value: Any, interaction: Optional[Interaction] = None):
        if self.folder:
            fld = self.config[self.folder.key].copy()
            fld[self.key] = value
            original_data = {self.folder.key: self.config[self.folder.key]}
            data_to_set = {self.folder.key: fld}
            conf_type = self.config.types[self.folder.key][self.key]  # type: ignore
        else:
            original_data = {self.key: self.config[self.key]}
            data_to_set = {self.key: value}
            conf_type = self.config.types[self.key]

        try:
            ret = await self.config.set(**data_to_set)
        except ConfigValueError:
            content = (
                interaction.message.content
                if interaction and interaction.message
                else ""
            )
            err = self.ctx.format_message("value_error")

            # this is not the best way, but I'm keeping this for now
            if not content.endswith(err):
                content += f"\n\n{err}"

            await self.set_disabled_items(False, interaction)
            if interaction and interaction.message:
                await interaction.followup.edit_message(
                    interaction.message.id, content=content
                )

            raise

        try:
            await conf_type.setup(self.ctx, value)
        except Exception:
            await self.config.set(**original_data)
            await self.set_disabled_items(True, interaction, keep_back=True)
            raise

        await self.config.fetch()

        # this time we're not editing the message because
        # it'll be edited later in this View's subclasses
        await self.set_disabled_items(False)
        return ret

    async def set_disabled_items(
        self,
        value: bool,
        /,
        interaction: Optional[Interaction] = None,
        *,
        keep_back: bool = False,
    ):
        self._setting_prop = value
        if keep_back:
            self._setting_prop = False

        for child in self.children:
            if not hasattr(child, "disabled"):
                continue

            custid = getattr(child, "custom_id", "")
            if custid == self.back.custom_id and keep_back:
                self.back.disabled = False
                continue

            child.disabled = value  #  type: ignore

        if interaction:
            try:
                await interaction.response.edit_message(view=self)
            except discord.InteractionResponded:
                await interaction.followup.edit_message(
                    interaction.message.id, view=self  # type: ignore
                )

    @ui.button(**BACK_BUTTON_PROPS)
    async def back(self, interaction: Interaction, button: ui.Button):
        return await items_back(self, interaction, button)


class BooleanPropertyView(PropertyView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        folder: Optional[FolderConfigData] = None,
        timeout: float = 180,
    ):
        super().__init__(ctx, config, key, parent, folder=folder, timeout=timeout)
        self.update_button_name()

    def update_button_name(self):
        self.toggler.label = self.ctx.format_message(
            "bool_" + ("disable" if self.value else "enable")
        )

    @ui.button(label="Toggle", custom_id="toggle", style=ButtonStyle.green)
    async def toggler(self, interaction: Interaction, button: ui.Button):
        self.value = not self.value
        await interaction.response.defer()
        await self.set(self.value, interaction)
        data = get_lang_props(self.ctx.language_to_use, self.key, self.folder)
        cont = CONFIG_TEMPLATE.format(
            name=data["name"], description=data["description"]
        )
        self.update_button_name()
        await interaction.followup.edit_message(interaction.message.id, content=cont, view=self)  # type: ignore


class CustomPropertyModal(Modal):
    def __init__(
        self, view: "CustomPropertyView", *, timeout: Optional[float] = None
    ) -> None:
        self.view = view
        data = get_lang_props(view.ctx.language_to_use, view.key, view.folder)
        super().__init__(view.ctx, title=data["name"], timeout=timeout)
        self.ctx = view.ctx

    @classmethod
    def create(cls, view: "CustomPropertyView", *, timeout: Optional[float] = None):
        if view.folder:
            cfg_type = view.config.types[view.folder.key][view.key]  # type: ignore
            value = view.config[view.folder.key][view.key]
        else:
            cfg_type = view.config.types[view.key]
            value = view.config[view.key]

        # clean up before using
        for k in cls.__modal_children_items__.copy():
            cls.__modal_children_items__.pop(k)
            delattr(cls, k)

        for k, v in cfg_type.inputs.items():
            if len(cfg_type.inputs) > 1:
                default = cfg_type.default[k]
                va = value[k]
            else:
                default = cfg_type.default
                va = value

            style = v or discord.TextStyle.short
            val = ui.TextInput(
                label=view.get_input_label(view.key, k, view.ctx, view.folder),
                style=style,
                placeholder=default,  #  type: ignore
                default=va,
                custom_id=k,
            )

            cls.__modal_children_items__[k] = val
            setattr(cls, k, val)

        return cls(view, timeout=timeout)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer()

        vals = {}
        for k, v in self.__modal_children_items__.copy().items():
            value = getattr(self, k).value
            v.default = value  #  type: ignore
            vals[k] = value

        if len(vals) > 1:
            await self.view.set(vals, interaction)
        else:
            await self.view.set(list(vals.values())[0], interaction)

        lang = get_lang_props(self.ctx.language_to_use, self.view.key, self.view.folder)

        cont = CONFIG_TEMPLATE.format(
            name=lang["name"], description=lang["description"]
        )

        inputs = (
            self.view.config.types[self.view.folder.key][
                self.view.key  #  type: ignore
            ].inputs
            if self.view.folder
            else self.view.config.types[self.view.key].inputs
        )

        curr = self.view.get_current(
            inputs, vals, self.ctx, self.view.key, self.view.folder
        )

        if len(inputs) > 1:
            m = curr
        else:
            m = self.ctx.format_message("current_conf", {"current": curr})

        cont += f"\n\n{m}"

        await interaction.followup.edit_message(
            interaction.message.id, content=cont, view=self.view  #  type: ignore
        )


class CustomPropertyView(PropertyView):

    @staticmethod
    def get_input_label(prop: str, key: str, ctx: StrapContext, folder=None):
        return (
            get_lang_props(ctx.language_to_use, prop, folder)
            .get("inputs", {})
            .get(key, key)
        )

    @classmethod
    def get_current(
        cls,
        inputs: Dict[str, discord.TextStyle],
        conf,
        ctx: StrapContext,
        key: str,
        folder=None,
    ):
        vals = []

        for k, v in inputs.items():
            text_style = v or discord.TextStyle.short
            is_short = text_style == discord.TextStyle.short
            sym = "`" * (1 if is_short else 3)
            n = "\n" if not is_short else ""
            head = ""
            if len(inputs) > 1:
                lb = cls.get_input_label(key, k, ctx, folder)
                head = f"**{lb}**:{n or ' '}" if len(inputs) > 1 else ""

            vals.append(f"{head}{sym}{n}{conf[k]}{n}{sym}")

        return "\n".join(vals)

    @ui.button(label="set")
    async def open_modal(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(CustomPropertyModal.create(self))


# please give me a better way to do this
class ChannelSelectMenu(ui.ChannelSelect):
    async def callback(self, interaction: Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class RoleSelectMenu(ui.RoleSelect):
    async def callback(self, interaction: Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class UserSelectMenu(ui.UserSelect):
    async def callback(self, interaction: Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class MentionableSelectMenu(ui.MentionableSelect):
    async def callback(self, interaction: Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class StringSelectMenu(ui.Select):
    async def callback(self, interaction: Interaction):
        return await self.view.callback(interaction, self)  # type: ignore


class SelectPropertyView(PropertyView):
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        folder: Optional[FolderConfigData] = None,
        options: Optional[List[SelectOption]] = None,
        timeout: float = 180,
    ):
        super().__init__(ctx, config, key, parent, folder=folder, timeout=timeout)
        self.config = config
        self.key = key
        self.ctx = ctx
        if folder:
            self.menu_type = tp = config.types[folder.key][key].select_menu_type  # type: ignore
        else:
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
                    opt.default = opt.value == (
                        config[folder][key] if folder else config[key]
                    )
                kws["options"] = options

            self.add_item(menu(**kws))

        self.add_item(self.back)

    async def callback(self, interaction: Interaction, select: ui.Select):
        await interaction.response.defer()
        if not self.menu_type:
            await self.back.callback(interaction)
            return

        if self.folder:
            val = self.config[self.folder.key][self.key]
        else:
            val = self.config[self.key]

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

        if self.menu_type.type == MenuType.string:
            items: ui.Select = discord.utils.get(
                self.children, custom_id="select"  #  type: ignore
            )
            for opt in items.options:
                opt.default = opt.value == val

        try:
            await self.set(val, interaction)
        except ConfigValueError:
            return
        except Exception:
            select.disabled = True
            await interaction.followup.edit_message(
                interaction.message.id, view=self  #  type: ignore
            )
            raise
        finally:
            if self.menu_type.type == MenuType.string:
                items: ui.Select = discord.utils.get(
                    self.children, custom_id="select"  #  type: ignore
                )
                for opt in items.options:
                    opt.default = opt.value == val
        lang = get_lang_props(self.ctx.language_to_use, self.key, self.folder)
        cont = CONFIG_TEMPLATE.format(
            name=lang["name"], description=lang["description"]
        )
        currs = self.get_current_configs(self.menu_type, self.ctx, val)
        if currs:
            if len(currs) == 1:
                curr = currs[0]
            else:
                curr = "\n- " + ("\n- ".join(currs))

            m = self.ctx.format_message("current_conf", {"current": curr})
            cont += f"\n\n{m}"

        await interaction.followup.edit_message(
            interaction.message.id, content=cont, view=self  # type: ignore
        )

    @staticmethod
    def get_current_configs(menu_type: SelectMenuType, ctx: StrapContext, current):
        ret = []
        # TODO: implement MenuType.mentionable
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
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        folder: Optional[FolderConfigData] = None,
    ):
        self.config = config
        self.key = key
        self.folder = folder
        self.ctx = ctx
        emojis = config.emojis
        self.data = get_lang_props(ctx.language_to_use, key, folder)
        if folder:
            emojis = folder.emojis

        super().__init__(
            style=ButtonStyle.green,
            label=self.data["name"],
            custom_id=key,
            emoji=emojis[key] or None,
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.config.fetch()
        self.data = get_lang_props(self.ctx.language_to_use, self.key, self.folder)
        kwargs = {"folder": self.folder}
        viewtype: Type[PropertyView] = PropertyView
        content = CONFIG_TEMPLATE.format(
            name=self.data["name"], description=self.data["description"]
        )
        current = ""
        if self.folder:
            conf = self.config[self.folder.key][self.key]
            conf_tp = self.config.types[self.folder.key][self.key]  # type: ignore
        else:
            conf = self.config[self.key]
            conf_tp = self.config.types[self.key]

        if isinstance(conf, bool):
            viewtype = BooleanPropertyView
        elif isinstance(conf_tp, dict):
            viewtype = FolderView
        elif conf_tp.custom:
            viewtype = CustomPropertyView
            if not isinstance(conf, dict):
                conf = {list(conf_tp.inputs.keys())[0]: conf}
            current = viewtype.get_current(
                conf_tp.inputs, conf, self.ctx, self.key, self.folder
            )
        elif conf_tp.select_menu_type != None:
            menu_type = conf_tp.select_menu_type
            viewtype = SelectPropertyView
            currents = viewtype.get_current_configs(menu_type, self.ctx, conf)
            if menu_type.type == MenuType.string:
                kwargs["options"] = await conf_tp.get_select_menu_values(self.ctx)  # type: ignore

            if len(currents) == 1:
                current = currents[0]
            elif currents:
                current = "\n- " + ("\n- ".join(currents))

        if current and len(conf_tp.inputs) <= 1:
            m = self.ctx.format_message("current_conf", {"current": current})
            content += f"\n\n{m}"
        elif current and len(conf_tp.inputs) > 1:
            content += f"\n\n{current}"

        view = viewtype(self.ctx, self.config, self.key, self.view, **kwargs)  # type: ignore
        await interaction.followup.edit_message(
            interaction.message.id, content=content, view=view  #  type: ignore
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
        self.types = config.types

        self.folder = None
        self.parent = parent
        if not parent:
            self.remove_item(self.back)

        self._set_buttons(ctx)

    def _set_buttons(self, ctx: StrapContext):
        for child in self.children:
            if not isinstance(child, ConfigButton):
                continue

            self.remove_item(child)

        ret = []
        for key, value in self.types.items():
            can_be_set = self.types[key].can_be_set(ctx.user_config, ctx.guild_config)
            if not can_be_set:
                continue

            btn = ConfigButton(ctx, self.config, key, self.folder)
            ret.append(btn)
            self.add_item(btn)

        return ret

    @ui.button(**BACK_BUTTON_PROPS)
    async def back(self, interaction: Interaction, button: ui.Button):
        if not self.parent:
            return

        content = self.ctx.format_message(self.parent.content)
        for child in self.parent.children:
            child.label = self.ctx.format_message(child.label_to_format)

        await interaction.response.edit_message(content=content, view=self.parent)


class FolderView(ConfigMenuView, PropertyView):
    # the folder param is only added for compatibility,
    # subfolders haven't been implemented yet
    def __init__(
        self,
        ctx: StrapContext,
        config: AnyConfig,
        key: str,
        parent=None,
        *,
        folder=None,
    ):
        PropertyView.__init__(self, ctx, config, key, parent)
        self.config = config
        self.key = key
        self.parent = parent
        self.data = get_lang_props(ctx.language_to_use, key, folder)
        self.types = config.types[key]
        self.folder = self.types

        self._set_buttons(ctx)

    @ui.button(**BACK_BUTTON_PROPS)
    async def back(self, interaction: Interaction, button: ui.Button):
        return await items_back(self, interaction, button)

    @property
    def content(self):
        return CONFIG_TEMPLATE.format(
            name=self.data["name"], description=self.data["description"]
        )


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

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        cfg = getattr(self.ctx, f"{self.custom_id}_config")
        view = ConfigMenuView(self.ctx, cfg, self.view)  #  type: ignore
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
