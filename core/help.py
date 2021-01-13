import discord
import json
import random
from discord.ext import commands
from difflib import get_close_matches


class HelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot
        lang = await ctx.get_lang()
        prefix = self.clean_prefix
        ergastolator = discord.utils.get(bot.get_all_members(), id=602819090012176384)
        vincy = discord.utils.get(bot.get_all_members(), id=726381259332386867)
        cogs = [bot.get_cog("Fun"), bot.get_cog("Moderation"), bot.get_cog("Music")]
        random.shuffle(cogs)
        cogs.append(bot.get_cog("Utilities"))
        embed = discord.Embed.from_dict(lang["embed"])
        embed.color = discord.Color.lighter_grey()
        embed.description = embed.description.format(prefix=prefix)
        embed.set_footer(
            text=embed.footer.text.format(vincy=vincy, ergastolator=ergastolator),
            icon_url=embed.footer.icon_url,
        )
        for cog in cogs:
            lang_ = await ctx.get_lang(cog, cog=True)
            commands = []
            for command in await self.filter_commands(
                cog.get_commands(),
                sort=True,
            ):
                cmd = lang_["commands"][command.qualified_name]
                if command.qualified_name != "help":
                    commands.append(
                        f"**{prefix + command.qualified_name}** "
                        + (
                            f"- {cmd['description']}\n"
                            if "description" in cmd
                            else (
                                f"- {command.short_doc}\n"
                                if command.short_doc
                                else "- No description.\n"
                            )
                        )
                    )

            cog_name = lang_["name"] if "name" in lang else cog.qualified_name

            embed.add_field(name=cog_name, value="".join(commands), inline=True)

        await self.get_destination().send(embed=embed)

    async def _get_help_embed(self, topic):
        if not await self.filter_commands([topic]):
            return

        db = self.context.bot.db.db["LangConfig"]
        members = await db.find_one({"_id": "members"})
        guilds = await db.find_one({"_id": "guilds"})
        if str(self.context.author.id) in members:
            member = members[str(self.context.author.id)]
            ret = json.load(open(f"core/languages/{member['language']}.json"))
        elif str(self.context.guild.id) in guilds:
            guild = guilds[str(self.context.guild.id)]
            ret = json.load(open(f"core/languages/{guild['language']}.json"))
        else:
            ret = json.load(open(f"core/languages/{self.bot.lang.default}.json"))

        lang = ret["cogs"][topic.cog.__class__.__name__]["commands"][
            topic.qualified_name
        ]
        ulang = await self.context.get_lang()

        embed = discord.Embed(
            title=f"**{self.get_command_signature(topic)}**",
            description=lang["description"]
            if "description" in lang
            else (
                topic.help.format(prefix=self.clean_prefix)
                if topic.help
                else "No message."
            ),
            color=discord.Color.lighter_grey(),
        )
        if "examples" in lang:
            examples = []
            for example in lang["examples"]:
                examples.append(
                    f"`{self.clean_prefix}{topic.qualified_name}{' ' + example if example else ''}`"
                )
            embed.add_field(name=ulang["example"], value="\n".join(examples))
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

        self.context.bot.logger.warning(str(error))

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
