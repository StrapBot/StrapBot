# StrapBot
A multifunction Discord bot, with multiple languages support, music, moderation, fun commands and YouTube news!

The bot is still being rewritten at the moment, not all features of the old one have been implemented yet.

Moderation commands are yet to be added.

## Translating
Translations are always welcome! You can send a pull request to [the languages repository](https://github.com/StrapBot/languages.git) translating the bot to your language.

## The server
The server is used for the YouTube news to work. It works using Google's [PubSubHubbub Hub](https://pubsubhubbub.appspot.com) to send requests to the server, which sends notifications to channels using webhooks. \
It should be always running to work correctly, and it's recommended to run it in a VPS or dedicated server. If you want to run it on a home server (such as a Raspberry Pi), make sure you have a **static** public IP and you set port forwarding correctly in your home network.

You can start the server by either running `python3 server.py` or by running `sanic --factory server:create`.

### The SERVER_REQUEST_URL environment variable
This environment variable is the hostname and port to send to the PubSubHubbub Hub so it can send notifications to the server, which then sends them to the channels.

If you set `SERVER_HOST` to `0.0.0.0`, you can omit that environment variable, as it will use the public IP instead. Otherwise, this is required.

Example: `http://123.231.132.213:1234`
