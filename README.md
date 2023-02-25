# StrapBot
A multifunction Discord bot, with multiple languages support, music, moderation, fun commands and YouTube news!

The bot is still being rewritten at the moment, not all features of the old one have been implemented yet.

## Features to be added
- Moderation commands;
- Music commands (without YouTube);
- YouTube news;
- Support for modals on config.

## Translating
Translations are always welcome! You can send a pull request to [the languages repository](https://github.com/StrapBot/langs.git) translating the bot to your language.

### The SERVER_REQUEST_URL environment variable
This environment variable is the hostname and port to send to PubSubHubbub to receive notifications.

If you set `SERVER_HOST` to `0.0.0.0`, you can omit that environment variable, as it will use the public IP instead. Otherwise, this is required.

Example: `http://123.231.132.213:1234`