# StrapBot
[![Chat](https://img.shields.io/discord/778341184007438377?logo=Discord&colorB=5865F2)](https://discord.gg/G4de45Bywg)

A multifunction Discord bot, with multiple languages support, music, moderation, fun commands and YouTube news!

The bot is still being rewritten at the moment, not all features of the old one have been implemented yet.

Moderation commands are yet to be added.

## License
This bot is licensed under the **GPLv3 License**, except for the `custom` folder, where you can add your very own code to add features to the bot that do NOT modify the core functionality of it.

## Translating
Translations are always welcome! You can send a pull request to [the languages repository](https://github.com/StrapBot/languages.git) translating the bot to your language.

## The server
The server is used for the YouTube news to work. It works using Google's [PubSubHubbub Hub](https://pubsubhubbub.appspot.com) to send requests to the server, which sends notifications to channels using webhooks. \
It should be always running to work correctly, and it's recommended to run it in a VPS or dedicated server. If you want to run it on a home server (such as a Raspberry Pi), make sure you have a **static** public IP and you set port forwarding correctly in your home network.

You can start the server by either running `python3 server.py` or by running `sanic --factory server:create`.