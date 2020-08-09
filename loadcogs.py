import os, shutil

def cogs(cogpath):
    files = os.listdir(cogpath)
    cogs = f"{cogpath}." + " ".join(files)

    cog = cogs.replace(".py", "").replace(" ", f" {cogpath}.").split()

    if f"{cogpath}.__pycache__" in cog:
        cog.remove(f"{cogpath}.__pycache__")
    if f"{cogpath}..DS_Store" in cog:
        cog.remove(f"{cogpath}..DS_Store")
    if f"{cogpath}..gitignore" in cog:
        cog.remove(f"{cogpath}..gitignore")

    return cog
#print(cogs("cogs"))
