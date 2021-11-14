import discord
import random
from core import commands
from asyncio import TimeoutError


class coreutils(commands.Cog, name="Coreutils Simulation (beta)"):
    def __init__(self, bot):
        self.bot = bot
        self.beta = True
        self.db = bot.db.get_cog_partition(self)

    @commands.command()
    async def ls(self, ctx, path="~"):
        """List your files with the specified path"""
        files = await self.get_dirs(ctx.author.id)
        if not path.startswith("/") and not path.startswith("~"):
            path = f"~/{path}"

        path = path.replace("~", "/home")
        if files == None:
            await self.db.find_one_and_update(
                {"_id": ctx.author.id},
                {"$set": {"home": {}}},
                upsert=True,
            )
            files = {"_id": ctx.author.id, "home": {}}

        tg = [x for x in path.split("/") if x]
        if path.startswith("/") and len(tg) != 0:
            tg[0] = f"/{tg[0]}"
        for dir in tg:
            try:
                files = files[dir.replace("/", "", 1)]
            except KeyError:
                return await ctx.send("No such file or directory")

        list_ = []
        if not isinstance(files, dict):
            return await ctx.send("Not a directory")
        for path, content in files.items():
            if isinstance(content, dict):
                list_.append(path + "/")
            else:
                list_.append(path)
        random.shuffle(list_)
        limit = 20
        list_ = [list_[i : i + limit] for i in range(0, len(list_), limit)]
        ret = []
        for tr in list_:
            _tr = "\t".join(tr)
            ret.append(f"```\n{_tr}\n```")
        if not ret:
            return await ctx.send("Directory is empty")
        await ctx.send(
            messages=ret, embed=discord.Embed(color=discord.Color.lighter_grey())
        )

    @commands.command()
    async def cat(self, ctx, file):
        """Get the content of a file"""
        files = await self.get_dirs(ctx.author.id)
        if not file.startswith("/"):
            file = f"~/{file}"

        file = file.replace("~", "/home")
        tg = [x for x in file.split("/") if x]
        if file.startswith("/") and len(tg) != 0:
            tg[0] = f"/{tg[0]}"
        for dir in tg:
            try:
                files = files[dir.replace("/", "", 1)]
            except KeyError:
                return await ctx.send("No such file or directory")

        if isinstance(files, bytes):
            files = files.decode("UTF-8")

        if files == "":
            return await ctx.send("File is empty.")

        await ctx.send(
            f"```\n{files}\n```" if not isinstance(files, dict) else "Is a directory"
        )

    @commands.command(usage="<file1> [file2] [file3] ...")
    async def touch(self, ctx, *, files):
        """Create a file"""
        files = files.split()
        _files = await self.get_dirs(ctx.author.id)
        paths = []
        if not files:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "file1"})()
            )
        for _file in files:
            file = _file
            files_ = _files
            if not file.startswith("/"):
                file = f"~/{file}"

            file = file.replace("~", "/home")
            tg = [x for x in file.split("/") if x]

            for dir in tg:
                if dir == tg[-1]:
                    break
                try:
                    files_ = files_[dir.replace("/", "", 1)]
                except KeyError:
                    return await ctx.send("No such file or directory")

            if tg[-1] in files_:
                if isinstance(files_[tg[-1]], dict):
                    await ctx.send(f"Error creating `{file}`: Directory exists.")
                else:
                    await ctx.send(f"Error creating `{file}`: File exists.")

            files_[tg[-1]] = ""
            paths.append(file)
            await self.db.find_one_and_update({"_id": ctx.author.id}, {"$set": _files})

        if len(paths) == 1:
            msg = f"Done. You can find your file at `{paths[0]}`"
        else:
            ns = "\n".join(paths)
            msg = f"Done. You can find your files at: **```fix\n{ns}\n```**"
        await ctx.send(msg)

    @commands.command(usage="<file1> [file2] [file3] ...")
    async def rm(self, ctx, files):
        """Delete a file"""
        files = files.split()
        _files = await self.get_dirs(ctx.author.id)
        _dirs = "-r" in files or "-rf" in files or "-fr" in files
        _force = "-f" in files or "-rf" in files or "-fr" in files
        _no_preserve_root = "--no-preserve-root" in files
        if "--no-preserve-root" in files:
            files.remove("--no-preserve-root")

        if "-r" in files:
            files.remove("-r")

        if "-f" in files:
            files.remove("-f")

        if "-rf" in files:
            files.remove("-rf")

        if "-fr" in files:
            files.remove("-fr")

        if not files:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "file1"})()
            )
        for _file in files:
            file = _file
            files_ = _files
            if not file.startswith("/"):
                file = f"~/{file}"

            file = file.replace("~", "/home")
            tg = [x for x in file.split("/") if x]
            if "/" in files:
                tg += ["/"]

            for dir in tg:
                if dir == tg[-1]:
                    break
                if dir == "/":
                    continue
                try:
                    files_ = files_[dir.replace("/", "", 1)]
                except KeyError:
                    return await ctx.send("No such file or directory")

            if not tg[-1] in files_ and tg[-1] != "/":
                return await ctx.send(
                    f"Error deleting `{file}`: No such file or directory."
                )

            if tg[-1] != "/":
                if isinstance(files_[tg[-1]], dict) and not _dirs:
                    return await ctx.send(
                        f"Error deleting `{file}`: Is a directory. You may use `-r` to force its deletion."
                    )

            if "/" in files:
                if not _dirs:
                    return await ctx.send(
                        "Error deleting `/`: Is a directory. You may use `-r` to force its deletion."
                    )
                if not _force:
                    return await ctx.send(
                        "Error deleting `/`: Permission denied. You may use `-rf` to force its deletion."
                    )

                if not _no_preserve_root:
                    return await ctx.send(
                        "It is very dangeours to work on `/`. You may use `--no-preserve-root` to force its deletion."
                    )

                message = await ctx.send(
                    embed=discord.Embed(
                        title="Wait, that's dangerous!",
                        description=(
                            "This will delete **ALL**  your data you saved here.\n"
                            'Please send "Yes, I know this is a very bad idea and I am going to lose all my data.", if you are.'
                        ),
                        color=discord.Color.red(),
                    )
                )

                def msgchk(m):
                    return m.author.id == ctx.author.id

                try:
                    msg = await self.bot.wait_for("message", check=msgchk, timeout=20)
                except TimeoutError:
                    return await message.edit(content="Aborted.")
                else:
                    if (
                        msg.content
                        == "Yes, I know this is a very bad idea and I am going to lose all my data."
                    ):
                        await self.db.delete_one({"_id": ctx.author.id})
                    else:
                        return await message.edit(content="Aborted.")
            else:
                del files_[tg[-1]]
                await self.db.find_one_and_update(
                    {"_id": ctx.author.id}, {"$set": _files}
                )

        await ctx.send("Done.")

    @commands.command()
    async def edit(self, ctx, file):
        await ctx.send("Coming late®!")

    @commands.command(usage="<dir1> [dir2] [dir3] ...")
    async def mkdir(self, ctx, files):
        """Create a file"""
        files = files.split()
        _files = await self.get_dirs(ctx.author.id)
        paths = []
        if not files:
            raise commands.MissingRequiredArgument(
                type("testù" + ("ù" * 100), (object,), {"name": "dir1"})()
            )
        for _file in files:
            file = _file
            files_ = _files
            if not file.startswith("/"):
                file = f"~/{file}"

            file = file.replace("~", "/home")
            tg = [x for x in file.split("/") if x]

            for dir in tg:
                if dir == tg[-1]:
                    break
                try:
                    files_ = files_[dir.replace("/", "", 1)]
                except KeyError:
                    return await ctx.send("No such file or directory")

            if tg[-1] in files_:
                if isinstance(files_[tg[-1]], dict):
                    await ctx.send(f"Error creating `{file}`: Directory exists.")
                else:
                    await ctx.send(f"Error creating `{file}`: File exists.")

                continue

            files_[tg[-1]] = {}
            paths.append(file + "/")
            await self.db.find_one_and_update({"_id": ctx.author.id}, {"$set": _files})

        if len(paths) == 1:
            msg = f"Done. You can find your directory at `{paths[0]}`"
        else:
            ns = "\n".join(paths)
            msg = f"Done. You can find your directories at: **```fix\n{ns}\n```**"
        await ctx.send(msg)

    async def get_dirs(self, id):
        ret = await self.db.find_one({"_id": id})
        if ret == None:
            await self.db.find_one_and_update(
                {"_id": id},
                {"$set": {"home": {}}},
                upsert=True,
            )
            ret = await self.db.find_one({"_id": id})

        ret.pop("_id")

        return ret


def setup(bot):
    bot.add_cog(coreutils(bot))
