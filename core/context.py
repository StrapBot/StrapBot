import typing
import os
import discord
import json
from discord.ext import commands
from discord.ext.commands.view import StringView
from .utils import get_lang
from typing_extensions import Self
from discord.utils import MISSING
from .config import GuildConfig, UserConfig


class StrapContext(commands.Context):
    __user_config: UserConfig = MISSING
    __guild_config: GuildConfig = MISSING

    def __init__(
        self,
        user_config: UserConfig = MISSING,
        guild_config: GuildConfig = MISSING,
        *,
        message: discord.Message,
        bot: commands.Bot,
        view: StringView,
        args: typing.List[typing.Any] = MISSING,
        kwargs: typing.Dict[str, typing.Any] = MISSING,
        prefix: typing.Optional[str] = None,
        command: typing.Optional[commands.Command] = None,
        invoked_with: typing.Optional[str] = None,
        invoked_parents: typing.List[str] = MISSING,
        invoked_subcommand: typing.Optional[commands.Command] = None,
        subcommand_passed: typing.Optional[str] = None,
        command_failed: bool = False,
        current_parameter: typing.Optional[commands.Parameter] = None,
        current_argument: typing.Optional[str] = None,
        interaction: typing.Optional[discord.Interaction] = None,
    ):
        super().__init__(
            message=message,
            bot=bot,
            view=view,
            args=args,
            kwargs=kwargs,
            prefix=prefix,
            command=command,
            invoked_with=invoked_with,
            invoked_parents=invoked_parents,
            invoked_subcommand=invoked_subcommand,
            subcommand_passed=subcommand_passed,
            command_failed=command_failed,
            current_parameter=current_parameter,
            current_argument=current_argument,
            interaction=interaction,
        )
        from strapbot import StrapBot

        self.bot: StrapBot = bot  # type: ignore
        if (user_config is MISSING and self.__user_config is MISSING) or (
            guild_config is MISSING and self.__guild_config is MISSING
        ):
            raise Exception("StrapContext must have both user and guild configs")
        else:
            if user_config is not MISSING:
                self.__user_config = user_config

            if guild_config is not MISSING:
                self.__guild_config = guild_config

    @classmethod
    def configure(
        cls, user_config: UserConfig, guild_config: GuildConfig
    ) -> typing.Type[Self]:
        cls.__user_config = user_config
        cls.__guild_config = guild_config

        return cls

    @property
    def config(self) -> UserConfig:
        """Alias for `user_config`."""
        return self.user_config

    @property
    def user_config(self) -> UserConfig:
        """The current user's settings"""
        return self.__user_config

    @property
    def guild_config(self) -> GuildConfig:
        """The current guild's settings."""
        return self.__guild_config

    @property
    def lang(self) -> typing.Optional[dict]:
        return get_lang(self.language_to_use, cog=self.cog, command=self.command)

    @property
    def guild_lang(self) -> typing.Optional[dict]:
        return get_lang(self.guild_config.lang, cog=self.cog, command=self.command)

    @property
    def user_lang(self) -> typing.Optional[dict]:
        return get_lang(self.config.lang, cog=self.cog, command=self.command)

    @property
    def language_to_use(self) -> str:
        val = self.config.lang
        if self.guild and self.guild_config.override_guild_lang:
            val = self.guild_config.lang

        return val

    def format_message(
        self, key, format: dict = {}, *, lang: typing.Optional[dict] = None
    ):
        lang = lang or self.lang
        if not lang:
            return key

        lang.pop("name", "")
        lang.pop("short_doc", "")
        lang.pop("details", "")
        if key in lang:
            return lang[key].format(**format)

        return key

    def format_embed(
        self,
        embed: discord.Embed,
        format: dict = {},
        *,
        lang: typing.Optional[dict] = None,
    ):
        # apparently converting the embed to
        # dict is the only way to modify fields
        emb = embed.to_dict()

        def _try_format(m) -> str:
            if m and len(m.strip().split()) == 1:
                return self.format_message(m, format, lang=lang)
            return m

        for field in emb.get("fields", []):
            field["name"] = _try_format(field["name"])
            field["value"] = _try_format(field["value"])

        emb["title"] = _try_format(embed.title)
        emb["description"] = _try_format(embed.description)

        if embed.author.name and "author" in emb:
            emb["author"]["name"] = _try_format(embed.author.name)

        if embed.footer.text and "footer" in emb:
            emb["footer"]["text"] = _try_format(embed.footer.text)

        return discord.Embed.from_dict(emb)

    def format_embeds(
        self,
        embeds: typing.Sequence[discord.Embed],
        format: dict = {},
        *,
        lang: typing.Optional[dict] = None,
    ):
        for embed in embeds:
            self.format_embed(embed, format, lang=lang)

        return embeds

    async def send(
        self,
        content: typing.Optional[str] = None,
        *,
        tts: bool = False,
        embed: typing.Optional[discord.Embed] = None,
        embeds: typing.Optional[typing.Sequence[discord.Embed]] = None,
        file: typing.Optional[discord.File] = None,
        files: typing.Optional[typing.Sequence[discord.File]] = None,
        stickers: typing.Optional[
            typing.Sequence[typing.Union[discord.GuildSticker, discord.StickerItem]]
        ] = None,
        delete_after: typing.Optional[float] = None,
        nonce: typing.Optional[typing.Union[str, int]] = None,
        allowed_mentions: typing.Optional[discord.AllowedMentions] = None,
        reference: typing.Optional[
            typing.Union[
                discord.Message, discord.MessageReference, discord.PartialMessage
            ]
        ] = None,
        mention_author: typing.Optional[bool] = None,
        view: typing.Optional[discord.ui.View] = None,
        suppress_embeds: bool = False,
        ephemeral: bool = False,
        **kws,
    ) -> discord.Message:

        if not isinstance(content, str) and content != None:
            raise TypeError(f"Expected None or an str object, got {content!r}")

        if embed and embeds:
            raise TypeError("Cannot mix embed and embeds keyword arguments.")

        if mention_author == None:
            mention_author = self.config.ping_on_reply

        if allowed_mentions == None:
            # mention_author will never be None
            new = discord.AllowedMentions(replied_user=mention_author)  #  type: ignore
            if self.bot.allowed_mentions != None:
                allowed_mentions = self.bot.allowed_mentions.merge(new)
            else:
                allowed_mentions = discord.AllowedMentions.none().merge(new)

        if content and len(content.strip().split()) == 1:
            content = self.format_message(content, kws)

        if embed:
            embed = self.format_embed(embed, kws)
        elif embeds:
            embeds = self.format_embeds(embeds, kws)

        return await super().send(
            content=content,
            tts=tts,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            stickers=stickers,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference or self.message.to_reference(),
            mention_author=mention_author,
            view=view,
            suppress_embeds=suppress_embeds,
            ephemeral=ephemeral,
        )

    async def send_as_help(
        self,
        content: typing.Optional[str] = None,
        *,
        tts: bool = False,
        embed: typing.Optional[discord.Embed] = None,
        embeds: typing.Optional[typing.Sequence[discord.Embed]] = None,
        file: typing.Optional[discord.File] = None,
        files: typing.Optional[typing.Sequence[discord.File]] = None,
        stickers: typing.Optional[
            typing.Sequence[typing.Union[discord.GuildSticker, discord.StickerItem]]
        ] = None,
        delete_after: typing.Optional[float] = None,
        nonce: typing.Optional[typing.Union[str, int]] = None,
        allowed_mentions: typing.Optional[discord.AllowedMentions] = None,
        reference: typing.Optional[
            typing.Union[
                discord.Message, discord.MessageReference, discord.PartialMessage
            ]
        ] = None,
        mention_author: typing.Optional[bool] = None,
        view: typing.Optional[discord.ui.View] = None,
        suppress_embeds: bool = False,
        ephemeral: bool = False,
        **kws,
    ):
        if not isinstance(content, str) and content != None:
            raise TypeError(f"Expected None or an str object, got {content!r}")

        if embed and embeds:
            raise TypeError("Cannot mix embed and embeds keyword arguments.")

        help_command = self.bot.help_command
        if help_command == None:
            raise ValueError("The help command is not set.")

        l = get_lang(self.config.lang, cog=help_command.cog, command=help_command)
        if content and len(content.strip().split()) == 1:
            content = self.format_message(content, kws, lang=l)

        if embed:
            embed = self.format_embed(embed, kws, lang=l)
        elif embeds:
            embeds = self.format_embeds(embeds, kws, lang=l)

        return await self.send(
            content=content,
            tts=tts,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            stickers=stickers,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference,
            mention_author=mention_author,
            view=view,
            suppress_embeds=suppress_embeds,
            ephemeral=ephemeral,
        )

    async def wait_for(
        self,
        event: str,
        /,
        *,
        check: typing.Optional[typing.Callable[..., bool]] = None,
        timeout: typing.Optional[float] = None,
    ) -> typing.Any:
        return await self.bot.wait_for(event, check=check, timeout=timeout)

    @staticmethod
    def get_command_signature(
        command: typing.Union[
            commands.Command,
            commands.HybridCommand,
            commands.Group,
            commands.HybridGroup,
        ],
        lang: str,
    ) -> str:
        """:class:`str`: Returns a POSIX-like signature useful for help command output."""
        cmd_lang = get_lang(lang, command=command) or {}

        if command.usage is not None:
            return cmd_lang.get("usage", command.usage)

        params = command.clean_params
        if not params:
            return ""

        lang_params = cmd_lang.get("params", {})
        result = []
        for name, param in params.items():
            greedy = isinstance(param.converter, commands.Greedy)
            optional = False  # postpone evaluation of if it's an optional argument

            annotation: typing.Any = (
                param.converter.converter if greedy else param.converter
            )
            origin = getattr(annotation, "__origin__", None)
            if not greedy and origin is typing.Union:
                none_cls = type(None)
                union_args = annotation.__args__
                optional = union_args[-1] is none_cls
                if len(union_args) == 2 and optional:
                    annotation = union_args[0]
                    origin = getattr(annotation, "__origin__", None)

            if name in lang_params:
                name = lang_params[name].get("name", name)

            if annotation is discord.Attachment:
                # For discord.Attachment we need to signal to the user that it's an attachment
                # It's not exactly pretty but it's enough to differentiate
                if optional or greedy:
                    result.append(f"[{name} (file)]")
                else:
                    result.append(f"<{name} (file)>")
                continue

            # for typing.Literal[...], typing.Optional[typing.Literal[...]], and Greedy[typing.Literal[...]], the
            # parameter signature is a literal list of it's values
            if origin is typing.Literal:
                name = "|".join(
                    f'"{v}"' if isinstance(v, str) else str(v)
                    for v in annotation.__args__
                )
            if not param.required:
                # We don't want None or '' to trigger the [name=value] case and instead it should
                # do [name] since [name=None] or [name=] are not exactly useful for the user.
                if param.displayed_default:
                    result.append(
                        f"[{name}={param.displayed_default}]"
                        if not greedy
                        else f"[{name}={param.displayed_default}]..."
                    )
                    continue
                else:
                    result.append(f"[{name}]")

            elif param.kind == param.VAR_POSITIONAL:
                if command.require_var_positional:
                    result.append(f"<{name}...>")
                else:
                    result.append(f"[{name}...]")
            elif greedy:
                result.append(f"[{name}]...")
            elif optional:
                result.append(f"[{name}]")
            else:
                result.append(f"<{name}>")

        return " ".join(result)

    @property
    def command_signature(self):
        if self.command == None:
            return ""

        return self.get_command_signature(self.command, self.config.lang)
