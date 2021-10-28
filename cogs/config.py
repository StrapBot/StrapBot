import os
import discord
from discord.ext import commands

type_ = type


class Config(commands.Cog):
    """Configure StrapBot!"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.lang.db

    @commands.command(aliases=["settings", "cfg"])
    async def config(self, ctx, type: str, key: str, *, value: str = None):
        """Configure StrapBot with your favorite settings."""
        if type == "server":
            type = "guild"
        elif type == "user":
            type = "author"

        embed = discord.Embed(color=discord.Color.red(), title=ctx.lang.error)

        if type not in ["author", "guild"]:
            embed.description = ctx.lang.errors.type
            await ctx.send(embed=embed)
            return

        id = getattr(ctx, type).id
        base = self.bot.config.get_base(self.bot.config.get_idtype(id))
        if key.lower() == "youtube" and type == "guild":
            await self.bot.get_command("youtube")(ctx, *(value or "").split())
            return

        if key.lower() not in base:
            keys = []
            requires = ctx.lang.requires
            for k, v in base.items():
                if v == None:
                    continue

                cls = v.__name__ if isinstance(v, type_) else type_(v).__name__
                requirement = f"{requires} {ctx.lang.types[cls]}"
                if cls in ["bool"]:  # made it a list so if I need more I can add it.
                    requirement = ctx.lang.types[cls]

                if k == "logchannel":
                    requirement += f" or {ctx.lang.types['channel']}"

                keys.append(f"**`{k}`**: {requirement}.")

            embed.description = ctx.lang.errors.key.format(
                key=key, keys="\n".join(keys)
            )
            await ctx.send(embed=embed)
            return

        if base[key] == bool:
            value = not await self.bot.config.get(id, key)

        try:
            await self.bot.config.set(id, ctx.lang.current, **{key: value})
        except Exception as exc:
            embed.description = str(exc)
        else:
            ctx.lang = await ctx.get_lang()
            embed.color = discord.Color.lighter_grey()
            embed.title = ctx.lang.success
            embed.description = ctx.lang.set.format(key=key, value=value)
            if base[key] == bool:
                embed.title = ctx.lang.configurations[key].title
                embed.description = ctx.lang.enabled if value else ctx.lang.disabled

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Config(bot))
