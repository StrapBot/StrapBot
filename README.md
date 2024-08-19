# StrapBot
[![Chat](https://img.shields.io/discord/778341184007438377?logo=Discord&colorB=5865F2)](https://discord.gg/G4de45Bywg)
[![Invite me!](https://img.shields.io/badge/invite%20me!-darkgreen)](https://discord.com/oauth2/authorize?client_id=740140581174378527&scope=bot&permissions=21206477878)


A multifunction Discord bot, with multiple languages support, moderation, text generation (using the Markov chain) and YouTube news!

## Self-hosting
### Requirements
- [Python 3.8+](https://www.python.org/downloads/)
- [A Discord bot token](https://discord.com/developers/applications)
- A MongoDB database
- A Google API key for the YouTube news
- PM2 for running the bot in the background (optional, but recommended) [requires Node.js]

1. Clone the repository: `git clone https://github.com/StrapBot/StrapBot.git`
    - You can also clone through SSH: `git clone git@github.com:StrapBot/StrapBot.git`, but you'll need to set up an SSH key and set the `PUBKEY_PATH`, `PRIVKEY_PATH` and `PRIVKEY_PASS` environment variables in the `.env` file.
    - If you don't want to pass the SSH key passphrase to the `.env` file, you can either create another key without it and only use it for the bot, or simply use HTTP.
2. Checkout into the latest release: ```cd StrapBot; git checkout $(git describe --tags `git rev-list --tags --max-count=1`)```
3. Install the dependencies: `pip install -Ur requirements.txt`
    - If you're setting up [the server](#the-server), you'll also need to install the server dependencies: `pip install -Ur requirements.server.txt`

4. Copy `example.env` to `.env` and fill in the required fields.
5. Run the bot: `python3 strapbot.py`

> Note: If you download the bot through the ZIP file from the releases page, the updater will not work.

### Running in the background
You can use PM2 to run the bot in the background.
To do so, copy the `ecosystem.config.example.js` file to `ecosystem.config.js` and adjust your Python path. \
Then, run `pm2 start --only strapbot` in the bot's directory to start the bot in the background. \
If you're setting up [the server](#the-server) in the same machine, instead, you can just run `pm2 start` to start both the bot and the server. \
Instead, if you're setting up the server in a different machine, you can run `pm2 start --only sb-server` in the bot's directory to only start the server in the background.

> Note: This must only be done the first time you add the bot to PM2.
> Once the bot has been started into PM2, you can use `pm2 ls` to view the list of processes. \
> If you do not know how PM2 works, you can find more information [here](https://pm2.keymetrics.io/docs/usage/quick-start/).

## License
This bot is licensed under the **GPL-3 License**, except for the `custom` folder, where you can add your very own code to add features to the bot that do NOT modify the core functionality of it without having to open-source it.

## Translating
Translations are always welcome! You can send a pull request to [the languages repository](https://github.com/StrapBot/languages.git) translating the bot to your language.

## The server
The server is used for the YouTube news to work. It works using Google's [PubSubHubbub Hub](https://pubsubhubbub.appspot.com) to send requests to the server, which sends notifications to channels using webhooks. \
It should be always running to work correctly, and it's recommended to run it in a VPS or dedicated server. If you want to run it on a home server (such as a Raspberry Pi), make sure you have a **static** public IP and you set port forwarding correctly in your home network.

You can start the server by either running `python3 server.py` or by running `sanic --factory server:create`.