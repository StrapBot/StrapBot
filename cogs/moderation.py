import asyncio
import discord
import random
from discord.ext import commands


class Moderation(commands.Cog):
    """
    Commands to moderate your server.
    """

    def __init__(self, bot):
        self.bot = bot
        self.ee = {}
        self.db = bot.db.get_cog_partition(self)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Sets up mute role permissions for the channel."""
        muterole = await self.db.find_one({"_id": "muterole"})
        if muterole == None:
            return

        if not str(channel.guild.id) in muterole:
            return

        role = channel.guild.get_role(muterole[str(channel.guild.id)])
        if role == None:
            return
        await channel.set_permissions(role, send_messages=False)

    @commands.command(usage="<channel>")
    @commands.has_permissions(manage_channels=True)
    async def setlog(self, ctx, channel: discord.TextChannel = None):
        """Sets up a log channel."""
        lang = await ctx.get_lang(self)
        if channel == None:
            return await ctx.send_help(ctx.command)

        try:
            await channel.send(
                embed=discord.Embed(
                    description=lang.test,
                    color=discord.Color.lighter_grey(),
                )
            )
        except discord.errors.Forbidden:
            embed = discord.Embed.from_dict(lang.embeds.error)
            embed.color = discord.Color.red()
            await ctx.send(embed=embed)
        else:
            await self.db.find_one_and_update(
                {"_id": "logging"},
                {"$set": {str(ctx.guild.id): channel.id}},
                upsert=True,
            )
            embed = discord.Embed.from_dict(lang.embeds.success)
            embed.description = embed.description.format(channel.mention)
            embed.color = discord.Color.lighter_grey()
            await ctx.send(embed=embed)

    @commands.command(usage="<role>")
    @commands.has_permissions(manage_roles=True)
    async def muterole(self, ctx, role: discord.Role = None):
        """Sets up the muted role."""
        lang = await ctx.get_lang(self)
        if role is None:
            if (await self.db.find_one({"_id": "muterole"})) is not None:
                if (
                    ctx.guild.get_role(
                        (await self.db.find_one({"_id": "muterole"}))[str(ctx.guild.id)]
                    )
                    != None
                ):
                    return await ctx.send(
                        embed=discord.Embed(
                            title="Error" + ("e" if lang.current == "it" else ""),
                            description=lang.error,
                            color=discord.Color.red(),
                        ).set_footer(text=lang.error_footer)
                    )
            role = await ctx.guild.create_role(name=lang.name)

        await self.db.find_one_and_update(
            {"_id": "muterole"}, {"$set": {str(ctx.guild.id): role.id}}, upsert=True
        )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(role.mention),
                color=discord.Color.lighter_grey(),
            )
        )

    @commands.command(usage="<member> [reason]")
    @commands.has_permissions(manage_guild=True)
    async def warn(self, ctx, member: discord.Member = None, *, reason=None):
        """
        Warns the specified member.
        """
        lang = await ctx.get_lang(self)
        user_lang = await self.bot.lang.fetch_user_lang(ctx, member.id)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)
        if member == None:
            return await ctx.send_help(ctx.command)

        if reason != None:
            if not (
                reason.endswith(".")
                and reason.endswith("!")
                and reason.endswith("?")
                and reason.endswith(",")
            ):
                reason = reason + "."

        case = await self.get_case(ctx)
        case = lang.case.format(case)
        guild_case_ = await self.get_guild_case(ctx)
        guild_case = guild_lang.case.format(guild_case_)

        msg = (user_lang.msg_ if reason else user_lang.msg).format(g=ctx.guild.name, r=reason)
        fp = "per" if guild_lang.current == "it" else "for"

        await self.log(
            guild=ctx.guild,
            embed=discord.Embed(
                title=guild_lang.warn,
                description=f"{member} {guild_lang.log} {ctx.author.mention}"
                + (f" {fp}: {reason}" if reason else "."),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=guild_case),
        )

        try:
            await member.send(msg)
        except discord.errors.Forbidden:
            return await ctx.send(
                embed=discord.Embed(
                    title="Logg" + ("ato" if lang.current == "it" else "ed"),
                    description=lang.logged.format(str(member)),
                    color=discord.Color.lighter_grey(),
                ).set_footer(text=case)
            )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(str(member)),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=case)
        )

    @commands.command(usage="<member> [reason]")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member = None, *, reason=None):
        """Kicks the specified member."""
        lang = await ctx.get_lang(self)
        if member == None:
            return await ctx.send_help(ctx.command)

        if reason != None:
            if not (
                reason.endswith(".")
                and reason.endswith("!")
                and reason.endswith("?")
                and reason.endswith(",")
            ):
                reason = reason + "."

        user_lang = await self.bot.lang.fetch_user_lang(ctx, member.id)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)

        msg = (user_lang.msg_ if reason else user_lang.msg).format(g=ctx.guild.name, r=reason)
        fp = "per" if guild_lang.current == "it" else "for"

        try:
            mesage = await member.send(msg)
        except discord.errors.Forbidden:
            mesage = None

        try:
            await member.kick(reason=reason)
        except discord.errors.Forbidden:
            if mesage != None:
                await mesage.delete()
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.error,
                    color=discord.Color.red(),
                ).set_footer(text=lang.fix)
            )

        case = await self.get_case(ctx)
        case = lang.case.format(case)
        guild_case_ = await self.get_guild_case(ctx)
        guild_case = guild_lang.case.format(guild_case_)

        await self.log(
            guild=ctx.guild,
            embed=discord.Embed(
                title="Kick",
                description=f"{member} {guild_lang.log} {ctx.author.mention}"
                + (f" {fp}: {reason}" if reason else "."),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=guild_case),
        )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(str(member)),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=case)
        )

    @commands.command(usage="<member> [reason]")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member = None, *, reason=None):
        """Bans the specified member."""
        lang = await ctx.get_lang(self)
        if member == None:
            return await ctx.send_help(ctx.command)

        if reason != None:
            if not (
                reason.endswith(".")
                and reason.endswith("!")
                and reason.endswith("?")
                and reason.endswith(",")
            ):
                reason = reason + "."

        user_lang = await self.bot.lang.fetch_user_lang(ctx, member.id)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)

        msg = (user_lang.msg_ if reason else user_lang.msg).format(g=ctx.guild.name, r=reason)
        fp = "per" if guild_lang.current == "it" else "for"

        try:
            mesage = await member.send(msg)
        except discord.errors.Forbidden:
            mesage = None

        try:
            await member.ban(reason=reason, delete_message_days=0)
        except discord.errors.Forbidden:
            if mesage != None:
                await mesage.delete()
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.error,
                    color=discord.Color.red(),
                ).set_footer(text=lang.fix)
            )

        case = await self.get_case(ctx)
        case = lang.case.format(case)
        guild_case_ = await self.get_guild_case(ctx)
        guild_case = guild_lang.case.format(guild_case_)

        await self.log(
            guild=ctx.guild,
            embed=discord.Embed(
                title="Ban",
                description=f"{member} {guild_lang.log} {ctx.author.mention}"
                + (f" {fp}: {reason}" if reason else "."),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=guild_case),
        )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(str(member)),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=case)
        )

    @commands.command(usage="<member> [reason]")
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member = None, *, reason=None):
        """Mutes the specified member."""
        lang = await ctx.get_lang(self)
        if member == None:
            return await ctx.send_help(ctx.command)
        role = await self.db.find_one({"_id": "muterole"})
        no_role = False
        if role == None:
            no_role = True
        elif str(ctx.guild.id) in role:
            role = ctx.guild.get_role(role[str(ctx.guild.id)])
            if role == None:
                no_role = True

        if reason != None:
            if not (
                reason.endswith(".")
                and reason.endswith("!")
                and reason.endswith("?")
                and reason.endswith(",")
            ):
                reason = reason + "."

        if no_role:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.notset.format(ctx.prefix),
                    color=discord.Color.red(),
                )
            )

        user_lang = await self.bot.lang.fetch_user_lang(ctx, member.id)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)

        msg = (user_lang.msg_ if reason else user_lang.msg).format(g=ctx.guild.name, r=reason)
        fp = "per" if guild_lang.current == "it" else "for"

        try:
            mesage = await member.send(msg)
        except discord.errors.Forbidden:
            mesage = None

        try:
            await member.add_roles(role, reason=reason)
        except discord.errors.Forbidden:
            if mesage != None:
                await mesage.delete()
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.error,
                    color=discord.Color.red(),
                ).set_footer(text=lang.fix)
            )

        case = await self.get_case(ctx)
        case = lang.case.format(case)
        guild_case_ = await self.get_guild_case(ctx)
        guild_case = guild_lang.case.format(guild_case_)

        await self.log(
            guild=ctx.guild,
            embed=discord.Embed(
                title="Mute",
                description=f"{member} {guild_lang.log} {ctx.author.mention}"
                + (f" {fp}: {reason}" if reason else "."),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=guild_case),
        )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(str(member)),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=case)
        )

    @commands.command(usage="<member> [reason]")
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member = None, *, reason=None):
        """Unmutes the specified member."""
        lang = await ctx.get_lang(self)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)
        if member == None:
            return await ctx.send_help(ctx.command)
        role = await self.db.find_one({"_id": "muterole"})
        no_role = False
        if role == None:
            no_role = True
        elif str(ctx.guild.id) in role:
            role = ctx.guild.get_role(role[str(ctx.guild.id)])
            if role == None:
                no_role = True

        if reason != None:
            if not (
                reason.endswith(".")
                and reason.endswith("!")
                and reason.endswith("?")
                and reason.endswith(",")
            ):
                reason = reason + "."

        if no_role:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.notset(),
                    color=discord.Color.red(),
                )
            )

        try:
            await member.remove_roles(role, reason=reason)
        except discord.errors.Forbidden:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.error,
                    color=discord.Color.red(),
                ).set_footer(text=lang.fix)
            )

        case = await self.get_case(ctx)
        case = lang.case.format(case)
        guild_case_ = await self.get_guild_case(ctx)
        guild_case = guild_lang.case.format(guild_case_)
        fp = "per" if guild_lang.current == "it" else "for"

        await self.log(
            guild=ctx.guild,
            embed=discord.Embed(
                title="Mute",
                description=f"{member} {guild_lang.log} {ctx.author.mention}"
                + (f" {fp}: {reason}" if reason else "."),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=guild_case),
        )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(str(member)),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=case)
        )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def nuke(self, ctx, channel: discord.TextChannel = None):
        """
        Nukes (deletes EVERY message in) a channel.
        You can mention a channel to nuke that one instead.
        """
        lang = await ctx.get_lang(self)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)
        if channel == None:
            channel = ctx.channel
        tot = lang.this if channel.id == ctx.channel.id else lang.that
        embed = discord.Embed.from_dict(lang.embeds.confirm)
        embed.description = embed.description.format(tot)
        embed.color = discord.Color.red()
        message = await ctx.send(
            embed=embed
        )

        def surecheck(m):
            return m.author == ctx.message.author

        try:
            sure = await self.bot.wait_for("message", check=surecheck, timeout=30)
        except asyncio.TimeoutError:
            await message.edit(
                embed=discord.Embed(
                    title=lang.aborted, color=discord.Color.lighter_grey()
                )
            )
            ensured = False
        else:
            if sure.content == lang.yes:
                ensured = True
            else:
                await message.edit(
                    embed=discord.Embed(
                        title=lang.aborted, color=discord.Color.lighter_grey()
                    )
                )
                ensured = False
        if ensured:
            case_ = await self.get_case(ctx)
            case = lang.case.format(case)
            guild_case = guild_lang.case.format(case)

            channel_position = channel.position

            try:
                new_channel = await channel.clone()

                await new_channel.edit(position=channel_position)
                await channel.delete()
            except discord.errors.Forbidden:
                return await ctx.send(
                    embed=discord.Embed(
                        title="Error" + ("e" if lang.current == "it" else ""),
                        description=lang.error.format(tot),
                        color=discord.Color.red(),
                    ).set_footer(text=lang.fix)
                )

            await new_channel.send(
                embed=discord.Embed(
                    title="Nuke",
                    description=lang.nuked,
                    color=discord.Color.lighter_grey(),
                )
                .set_image(
                    url="https://cdn.discordapp.com/attachments/600843048724987925/600843407228928011/tenor.gif"
                )
                .set_footer(text=case)
            )

            await self.log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Nuke",
                    description=f"{ctx.author.mention} {guild_lang.log} {new_channel.mention}.",
                    color=discord.Color.lighter_grey(),
                ).set_footer(text=guild_case),
            )

    @commands.command(usage="<amount>", aliases=["clear"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 1):
        """Purge the specified amount of messages."""
        lang = await ctx.get_lang(self)
        guild_lang = await self.bot.lang.fetch_guild_lang(ctx)
        max = 2000
        if amount <= 0:
            if not str(ctx.author.id) in self.ee:
                self.ee[str(ctx.author.id)] = 0
            else:
                self.ee[str(ctx.author.id)] += 1

            if self.ee[str(ctx.author.id)] == 4:
                self.ee[str(ctx.author.id)] = 0
                return await ctx.send(random.choice(["lol no", "bruh"]))

            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.lt1,
                    color=discord.Color.red(),
                )
            )
        if amount > max:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.ut2,
                    color=discord.Color.red(),
                ).set_footer(text=lang.use_nuke.format(ctx.prefix))
            )

        try:
            await ctx.message.delete()
            await ctx.channel.purge(limit=amount)
        except discord.errors.Forbidden:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error" + ("e" if lang.current == "it" else ""),
                    description=lang.error,
                    color=discord.Color.red(),
                ).set_footer(text=lang.fix)
            )


        case = await self.get_case(ctx)
        case = lang.case.format(case)
        guild_case_ = await self.get_guild_case(ctx)
        guild_case = guild_lang.case.format(guild_case_)
        messages = lang.message if amount == 1 else lang.messages
        messages_ = guild_lang.message if amount == 1 else guild_lang.messages
        have = guild_lang.have if amount == 1 else guild_lang.has

        await self.log(
            guild=ctx.guild,
            embed=discord.Embed(
                title="Purge",
                description=f"{amount} {messages_} {have} {guild_lang.by} {ctx.author.mention}.",
                color=discord.Color.lighter_grey(),
            ).set_footer(text=guild_case),
        )

        await ctx.send(
            embed=discord.Embed(
                title=lang.success,
                description=lang.done.format(amount, messages),
                color=discord.Color.lighter_grey(),
            ).set_footer(text=case)
        )

    async def get_case(self, ctx):
        """Gives the case number."""
        lang = (await ctx.get_lang(self)).current
        num = await self.db.find_one({"_id": "cases"})
        if num == None:
            num = 0
        elif str(ctx.guild.id) in num:
            num = num[str(ctx.guild.id)]
            num = int(num)
        else:
            num = 0
        num += 1
        await self.db.find_one_and_update(
            {"_id": "cases"}, {"$set": {str(ctx.guild.id): num}}, upsert=True
        )
        prefix = ""
        suffix = ["th", "st", "nd", "rd", "th"][min(num % 10, 4)]
        if 11 <= (num % 100) <= 13:
            suffix = "th"
        if lang == "it":
            suffix = ""
            prefix = "n°"
        return f"{prefix}{num}{suffix}"

    async def get_guild_case(self, ctx):
        """Gives the case number."""
        lang = (await self.bot.lang.fetch_guild_lang(ctx)).current
        num = await self.db.find_one({"_id": "cases"})
        if num == None:
            num = 0
        elif str(ctx.guild.id) in num:
            num = num[str(ctx.guild.id)]
            num = int(num)
        else:
            num = 0
        num += 1
        await self.db.find_one_and_update(
            {"_id": "cases"}, {"$set": {str(ctx.guild.id): num}}, upsert=True
        )
        prefix = ""
        suffix = ["th", "st", "nd", "rd", "th"][min(num % 10, 4)]
        if 11 <= (num % 100) <= 13:
            suffix = "th"
        if lang == "it":
            suffix = ""
            prefix = "n°"
        return f"{prefix}{num}{suffix}"

    async def log(self, guild: discord.Guild, embed: discord.Embed):
        """Sends logs to the log channel."""
        channel = await self.db.find_one({"_id": "logging"})
        if channel == None:
            return
        if not str(guild.id) in channel:
            return
        channel = self.bot.get_channel(channel[str(guild.id)])
        if channel == None:
            return
        return await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Moderation(bot))  # TODO: translate this
