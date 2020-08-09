import os, shutil

def cogs():
    files = os.listdir("cogs")
    cogs = f"cogs." + " ".join(files)
    cog = cogs.replace(".py", "").replace(" ", f" cogs.").split()
    #TODO: Remove all the files that don't end with .py from the list.
    if f"cogs.__pycache__" in cog:
        cog.remove(f"cogs.__pycache__")
    if f"cogs..DS_Store" in cog:
        cog.remove(f"cogs..DS_Store")
    if f"cogs..gitignore" in cog:
        cog.remove(f"cogs..gitignore")
    return cog

#print(cogs())
