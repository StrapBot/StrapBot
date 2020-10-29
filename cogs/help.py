import discord
import random
from discord.ext import commands
from difflib import get_close_matches


class HelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot
        prefix = self.clean_prefix
        cogs = [bot.get_cog("Test"), bot.get_cog("Fun"), bot.get_cog("Music")]
        random.shuffle(cogs)
        lang = await ctx.get_lang(self.cog)
        embed = discord.Embed.from_dict(lang["embed"])
        embed.color = discord.Color.lighter_grey()
        embed.description = embed.description.format(prefix=prefix)
        for cog in cogs:
            commands = []
            for command in await self.filter_commands(
                cog.get_commands(),
                sort=True,
            ):
                commands.append(
                    f"**{prefix + command.qualified_name}** "
                    + (
                        f"- {command.short_doc}\n"
                        if command.short_doc != ""
                        else "- No description.\n"
                    )
                )

            embed.add_field(
                name=cog.qualified_name, value="".join(commands), inline=True
            )

        await self.get_destination().send(embed=embed)

    async def _get_help_embed(self, topic):
        if not await self.filter_commands([topic]):
            return

        embed = discord.Embed(
            title=f"**{self.get_command_signature(topic)}**",
            description=topic.help.format(prefix=self.clean_prefix)
            if topic.help
            else "No message.",
            color=discord.Color.lighter_grey(),
        )
        return embed

    async def send_cog_help(self, cog):
        prefix = self.clean_prefix
        commands = []
        for command in await self.filter_commands(
            cog.get_commands(),
            sort=True,
        ):
            commands.append(
                f"**{prefix + command.qualified_name}** "
                + (
                    f"- {command.short_doc}\n"
                    if command.short_doc != ""
                    else "- No description.\n"
                )
            )

        await self.get_destination().send(
            embed=discord.Embed(
                description=cog.description, color=discord.Color.lighter_grey()
            )
            .set_author(
                name=f"{cog.qualified_name} - Help",
                icon_url=self.context.bot.user.avatar_url,
            )
            .add_field(
                name="Commands",
                value="".join(commands) if len(commands) != 0 else "No commands.",
            )
        )

    async def send_command_help(self, command):
        topic = await self._get_help_embed(command)
        if topic is not None:
            await self.get_destination().send(embed=topic)

    async def send_group_help(self, group):
        topic = await self._get_help_embed(group)
        if topic is None:
            return
        embed = topic

        format_ = ""
        length = len(group.commands)

        for i, command in enumerate(
            await self.filter_commands(group.commands, sort=True, key=lambda c: c.name)
        ):
            format_ += f"**{command.name}** - {command.short_doc}\n"

        if format_ != "":
            embed.add_field(name="Subcommands", value=format_[:1024], inline=False)

        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error):
        command = self.context.kwargs.get("command")

        print(error)

        embed = discord.Embed(color=discord.Color.red())
        embed.set_author(name="StrapBot", icon_url=self.context.bot.user.avatar_url)
        embed.set_footer(
            text=f'Command/category "{command}" not found.',
        )

        choices = set()

        for cmd in self.context.bot.walk_commands():
            if not cmd.hidden:
                choices.add(cmd.qualified_name)

        closest = get_close_matches(command, choices)
        if closest:
            embed.add_field(
                name="Did you mean:", value="\n".join(f"`{x}`" for x in closest)
            )
        else:
            embed.title = "Could not find command or category."
        await self.get_destination().send(embed=embed)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand(
            command_attrs={
                "name": "help",
                "aliases": ["man", "h"],
                "help": "Shows this message.",
            }
        )
        bot.help_command.cog = self

        def cog_unload(self):
            self.bot.help_command = self._original_help_command


def setup(bot):
    bot.add_cog(Help(bot))
