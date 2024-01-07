import os
import typing
import json
import discord
from discord import ui
from discord.ext import commands
from discord.interactions import Interaction
from .context import StrapContext
from .utils import get_lang, LANGS_PATH, DEFAULT_LANG_ENV

# for some reason I want to put help views
# here instead of the views folder


class CogHelpView(ui.View):
    def __init__(
        self,
        cmd: "StrapBotHelp",
        cog: commands.Cog,
        oldview: "HelpView",
        *,
        timeout: float = 180,
    ):
        super().__init__(timeout=timeout)
        self.cmd = cmd
        self.cog = cog
        self.view = oldview

    @ui.button(custom_id="back", emoji="⬅️", style=discord.ButtonStyle.blurple)
    async def back(self, interaction: Interaction, button: ui.Button):
        self.view.current_cog = None
        await interaction.response.edit_message(
            embed=self.cmd.context.format_embed(
                self.cmd.get_bot_help(self.view.mapping)
            ),
            view=self.view,
        )
        self.stop()

    async def on_timeout(self) -> None:
        try:
            await self.view.cmd.context.message.edit(view=None)
        except Exception:
            pass
        return await super().on_timeout()


class CogButton(ui.Button):
    def __init__(self, cmd: "StrapBotHelp", cog: commands.Cog, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd
        self.cog = cog
        self.view: HelpView

    async def callback(self, interaction: Interaction):
        self.view.current_cog = self.cog

        await interaction.response.edit_message(
            embed=self.cmd.context.format_embed(await self.cmd.get_cog_help(self.cog)),
            view=CogHelpView(self.cmd, self.cog, self.view),
        )


class HelpView(ui.View):
    def __init__(self, mapping, cmd: "StrapBotHelp", *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.current_cog: typing.Optional[commands.Cog] = None
        self.cmd = cmd
        self.mapping = mapping
        for cog in mapping.keys():
            cog: commands.Cog
            if not cog:
                continue

            b = CogButton(
                cmd,
                cog,
                label=cmd.get_cog_name(cog),
                custom_id=type(cog).__name__,
                style=discord.ButtonStyle.green,
                emoji=getattr(cog, "emoji", None),
            )
            self.add_item(b)

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        return (
            interaction.user.id == self.cmd.context.author.id
            and self.current_cog == None
        )

    async def on_timeout(self) -> None:
        try:
            await self.cmd.context.message.edit(view=None)
        except Exception:
            pass


class StrapBotHelp(commands.HelpCommand):
    context: StrapContext

    @property
    def lang(self):
        return get_lang(self.context.language_to_use, cog=self.cog, command=self)

    def _get_cog_path(
        self, cog: commands.Cog, lang: typing.Optional[str] = None
    ) -> str:
        p = os.path.abspath("./langs")
        cname = type(cog).__name__
        return os.path.join(p, lang or self.context.language_to_use, "cogs", cname)

    def _get_cog_lang_file(self, cog: commands.Cog, path: str) -> str:
        fp = os.path.join(self._get_cog_path(cog), path)
        if not os.path.exists(fp):
            deflang = os.getenv(DEFAULT_LANG_ENV, "en")
            fp = os.path.join(self._get_cog_path(cog, deflang), path)

        return fp

    def get_cog_name(self, cog: commands.Cog) -> str:
        fp = self._get_cog_lang_file(cog, "__data__.json")
        if not os.path.exists(fp):
            return cog.__cog_name__

        data = json.load(open(fp))
        return data["name"]

    def get_cog_description(self, cog: commands.Cog) -> str:
        fp = self._get_cog_lang_file(cog, "__description__.md")
        if not os.path.exists(fp):
            return cog.__cog_description__

        f = open(fp)
        ret = f.read()
        f.close()
        return ret

    def _get_help_text(self):
        official = os.getenv("OFFICIAL", "0") == "1"
        basedonsb = (
            self.context.format_message("based_on_strapbot", lang=self.lang)
            if not official
            else ""
        )
        invite_link = (
            "https://discord.com/oauth2/authorize?"
            f"client_id={self.context.me.id}"
            "&permissions=395945573431"
            "&scope=bot%20applications.commands"
        )
        my_guild = self.context.format_message(
            "my_server", {"my_guild": "https://discord.gg/G4de45Bywg"}, lang=self.lang
        )
        path = f"langs/{self.context.language_to_use}/help.md"
        if not os.path.exists(path):
            deflang = os.getenv(DEFAULT_LANG_ENV, "en")
            path = f"langs/{deflang}/help.md"

        ret = (
            open(path)
            .read()
            .format(
                bot_name=self.context.me.name,
                maybe_based_on_sb=basedonsb,
                invite_link=invite_link,
                maybe_my_server=my_guild,
            )
        )
        return ret.strip()

    def get_bot_help(self, mapping):
        return (
            discord.Embed(
                description=self._get_help_text(), color=self.context.me.accent_color
            )
            .set_footer(
                text="footer",
                icon_url=self.context.me.avatar,
            )
            .set_author(name="title", icon_url=self.context.me.avatar)
        )

    async def send_bot_help(self, mapping: dict[commands.Cog, list]):
        async with self.context.typing():
            for cog in mapping.copy().keys():
                # please always add commands to a cog, at least to Utilities
                if not cog:
                    continue
                check = await discord.utils.maybe_coroutine(cog.cog_check, self.context)
                if not check:
                    mapping.pop(cog)

            # for future forkers,
            # NOTE: Only write code from this comment on:
            #       the code above removes the cogs that
            #       the user can't run from mapping.
            await self.context.send_as_help(
                embed=self.get_bot_help(mapping), view=HelpView(mapping, self)
            )

    async def get_cog_help(self, cog: commands.Cog):
        p = self.context.clean_prefix
        check = await discord.utils.maybe_coroutine(cog.cog_check, self.context)
        cmds = []
        for cmd in cog.walk_commands():
            if cmd.parent:
                continue

            chks = check
            for chk in cmd.checks:
                chks = chks and await discord.utils.maybe_coroutine(chk, self.context)

            if not chks:
                continue

            cmds.append(f"`{p}{cmd.qualified_name}`")

        commands_ = f", ".join(cmds)
        footer = self.context.format_message(
            "cog_help_footer", {"prefix": p}, lang=self.lang
        )
        ret = (
            discord.Embed(
                description=self.get_cog_description(cog),
                color=self.context.me.accent_color,
            )
            .set_author(name=self.get_cog_name(cog), icon_url=self.context.me.avatar)
            .set_footer(text=footer, icon_url=self.context.me.avatar)
        )
        if commands_:
            ret.add_field(name="cog_commands_field_title", value=commands_)

        return ret

    async def send_cog_help(self, cog: commands.Cog):
        async with self.context.typing():
            await self.context.send_as_help(embed=await self.get_cog_help(cog))

    def get_command_signature(
        self,
        command: typing.Union[
            commands.Command,
            commands.HybridCommand,
            commands.Group,
            commands.HybridGroup,
        ],
        /,
    ) -> str:
        parent: typing.Optional[commands.Group] = command.parent  # type: ignore # the parent will be a Group
        entries = []
        while parent is not None:
            if not parent.signature or parent.invoke_without_command:
                entries.append(parent.name)
            else:
                entries.append(parent.name + " " + parent.signature)
            parent = parent.parent  # type: ignore
        parent_sig = " ".join(reversed(entries))

        if len(command.aliases) > 0:
            aliases = "|".join(command.aliases)
            fmt = f"[{command.name}|{aliases}]"
            if parent_sig:
                fmt = parent_sig + " " + fmt
            alias = fmt
        else:
            alias = command.name if not parent_sig else parent_sig + " " + command.name

        signature = self.context.get_command_signature(
            command, self.context.language_to_use
        )
        return f"{self.context.clean_prefix}{alias} {signature}"

    async def get_command_help(
        self,
        command: typing.Union[
            commands.Command,
            commands.HybridCommand,
            commands.Group,
            commands.HybridGroup,
        ],
    ):
        lang = get_lang(self.context.language_to_use, command=command) or {}
        desc = lang.get("short_doc", command.short_doc)
        if "details" in lang:
            desc += f"\n{lang['details']}"

        if not "short_doc" in lang:
            desc = command.help

        embed = discord.Embed(
            title=f"`{self.get_command_signature(command).strip()}`",
            description=desc or "command_no_description",
            color=self.context.me.accent_color,
        )
        if isinstance(command, (commands.Group, commands.HybridGroup)):
            cmds = [cmd.name for cmd in command.walk_commands()]
            lst = [f"`{c}`" for c in cmds]
            embed.add_field(name="subcommands_field_title", value=", ".join(lst))

        params = lang.get("params", {})
        cmd_params = command.clean_params
        parameters = []
        if cmd_params:
            for name, param in cmd_params.items():
                if name not in params:
                    continue

                props = params[name]
                if "name" not in props or "description" not in props:
                    continue

                p = "+" if param.required else "-"
                parameters.append(f"{p} **`{props['name']}`**: {props['description']}")

            if parameters:
                embed.add_field(name="params_field_title", value="\n".join(parameters))

        footer = "user_has"
        if not await command.can_run(self.context):
            footer += "_no"
        footer += "_permissions"

        embed.set_footer(text=footer, icon_url=self.context.me.avatar)
        return embed

    async def send_group_help(
        self, group: typing.Union[commands.Group, commands.HybridGroup]
    ) -> None:
        async with self.context.typing():
            await self.context.send_as_help(embed=await self.get_command_help(group))

    async def send_command_help(
        self, command: typing.Union[commands.Command, commands.HybridCommand]
    ):
        async with self.context.typing():
            await self.context.send_as_help(embed=await self.get_command_help(command))

    def get_cog_translations(self, cog: commands.Cog) -> typing.Dict[str, commands.Cog]:
        cog_name = type(cog).__name__
        names: dict[str, commands.Cog] = {
            cog_name: cog,
            cog.__cog_name__: cog,
            cog_name.lower(): cog,
            cog.__cog_name__.lower(): cog,
        }
        lang = self.context.language_to_use
        default_lang = os.getenv(DEFAULT_LANG_ENV, "en")
        lpaths = [
            os.path.join(LANGS_PATH, lang),
            os.path.join(LANGS_PATH, default_lang),
        ]
        for d in lpaths:
            path = os.path.join(LANGS_PATH, d, "cogs", cog_name, "__data__.json")
            if not os.path.exists(path):
                continue

            data = json.load(open(path))
            name = data["name"]
            names[name] = cog
            names[name.split()[0]] = cog
            names[name.lower()] = cog
            names[name.lower().split()[0]] = cog

        return names

    def get_cogs_translations(self) -> typing.Dict[str, commands.Cog]:
        names: dict[str, commands.Cog] = {}
        for cog in self.context.bot.cogs.values():
            names.update(self.get_cog_translations(cog))

        return names

    async def command_not_found(self, string: str, /) -> typing.Optional[dict]:
        cogs_maybe = self.get_cogs_translations()
        if string in cogs_maybe:
            return await self.send_cog_help(cogs_maybe[string])

        return {"text": "command_not_found", "name": string}

    async def subcommand_not_found(
        self, command: commands.Command, string: str, /
    ) -> dict:
        return {
            "text": "subcommand_not_found",
            "name": command.qualified_name,
            "subname": string,
        }

    async def send_error_message(
        self, error: typing.Optional[typing.Union[str, typing.Dict[str, typing.Any]]], /
    ) -> None:
        async with self.context.typing():
            fmt = {}
            if isinstance(error, str):
                text = error
            elif isinstance(error, dict):
                text = error.pop("text", None)
                fmt = error
                if text == None:
                    return
            else:
                return

            await self.context.send_as_help(text, **fmt)
