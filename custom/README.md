# Custom Files

Welcome, developers! This is the directory where the fun begins!

In this part of the code, you can add your own commands and features to the bot, as long as they don't modify its core functionality.

This directory contains examples for adding your own features and settings to the bot. If you're looking to create a guild extension without self-hosting the bot, you will only need [this example file](https://github.com/StrapBot/StrapBot/blob/main/custom/cogs/custom_extension.py.example) as a base for your extension. You can then submit your code for approval by running `sb.extend`, passing the file URL as an argument, or by uploading it as an attachment. **Before submitting, please read the [Extension Guidelines](#extension-guidelines).**

> **Note**: If you need to modify the core functionality of the bot, you can use the [`cogs`](https://github.com/StrapBot/StrapBot/blob/main/cogs) directory. However, you must keep your fork open-source as required by the [`GPL-3.0` License](https://github.com/StrapBot/StrapBot/blob/main/LICENSE).

## Extension Guidelines

1. **One Extension per Guild**
    - If you need to add new commands, you must run the `extend` command again with the new code and wait for re-approval.

2. **Test Before Submitting**
    - Ensure your extension is **__thoroughly tested__** before submission. The bot will ignore errors from guild extensions and will not load them if many errors occur in a short period. It will be annoying for both *you* and *whoever approves the code*, as you will have to debug the whole code over and over again, and it will have to be re-approved each time.
    - The bot is designed to work on **Python 3.9 and higher**, so it is a good idea to develop and test your code on that version.

3. **Code Availability**
    - Your extension's code must be available on a website or a public Git repository, at least until it gets approved.
    - If using a Git repository, you have two options:
        - Name your file `main.py` for automatic detection by the bot.
        - Specify the file name when running the `extend` command, e.g., `sb.extend https://github.com/octocat/Hello-World helloworld.py`.
    - If you don't have a website or Git repository, you can upload your file on Discord and use it as an attachment when executing the command.

4. **No Malicious Code**
    - Do not include backdoors or malicious code. **Repeated attempts will lead to a ban from this feature!**

5. **Follow the Discord Terms of Service**
    - This one should be common sense, and this one rule should be self-explanatory, but extensions that do not follow the [Discord ToS](https://discord.com/terms) will not be accepted.

*Please note that these guidelines are subject to change, so you should always review them to ensure your code remains compliant.*