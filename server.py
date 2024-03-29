"""Server for receiving requests from Google's PubSubHubbub Hub."""

import os
import sanic
import json
import xmltodict
import asyncio
from aiohttp import ClientSession
from sanic import Request, response
from sanic.request import RequestParameters
from sanic.log import logger, error_logger, server_logger, Colors
from dotenv import load_dotenv
from traceback import format_exc
from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticClient, AgnosticCollection
from discord import Webhook, NotFound, File, AllowedMentions
from io import BytesIO
from typing import Optional

load_dotenv()
app = sanic.Sanic("strapbot_server")
mongo: Optional[AgnosticClient] = None
db: Optional[AgnosticCollection] = None


class ReceivedChallenge(Exception):
    def __init__(self, args: RequestParameters) -> None:
        super().__init__()
        self.args = tuple(args.values())
        self.challenge = args.get("hub.challenge", None) or ""
        self.reqa = args

    def __str__(self):
        return f"Challenge `{self.reqa.get('hub.challenge')}` received."


async def send_requrl_to_db(url):
    internal_db = mongo.Internal  #  type: ignore
    await internal_db.update_one({"_id": "server"}, {"$set": {"request_url": url}}, upsert=True)  # type: ignore


async def get_request_url():
    req_url = app.ctx.request_url
    if not req_url and app.ctx.host == "0.0.0.0":
        async with ClientSession() as session:
            async with session.get("http://ifconfig.me/ip") as resp:
                req_url = (
                    f"http://{(await resp.content.read()).decode()}:{app.ctx.port}"
                )

    await send_requrl_to_db(req_url)
    return req_url


async def request_pubsubhubbub(
    channel_id: str, subscribe: bool, raise_for_status: bool = True
):
    data = {
        "hub.callback": f"{await get_request_url()}/notify",
        "hub.topic": f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}",
        "hub.verify": "sync",
        "hub.mode": f"{'un' if not subscribe else ''}subscribe",
        "hub.verify_token": "",
        "hub.secret": "",
        "hub.lease_seconds": "",
    }
    async with ClientSession() as session:
        async with session.post(
            "https://pubsubhubbub.appspot.com/subscribe", data=data
        ) as resp:
            if raise_for_status:
                resp.raise_for_status()


async def send_new_video(
    webhook_url: str,
    name: str,
    url: str,
    guild_id: int,
    channel_id: int,
    channel_name: str,
    channel_url: str,
    yt_channel_id: str,
):
    async with ClientSession() as session:
        try:
            webhook = await Webhook.from_url(
                webhook_url, session=session, bot_token=os.getenv("TOKEN")
            ).fetch()
        except NotFound:
            guilds_db = mongo.YouTubeNewsGuilds  #  type: ignore
            gdata = await guilds_db.find_one({"_id": guild_id})
            if not gdata.get("needs_new_webhook", False):
                await guilds_db.update_one(
                    {"_id": guild_id}, {"$set": {"needs_new_webhook": True}}
                )
        else:
            cfgdb: AgnosticCollection = mongo.Configurations  #  type: ignore
            guild_config: dict = await cfgdb.find_one({"_id": webhook.guild_id})  # type: ignore
            default = "{url}"
            msg = guild_config.get("yt_news_message", None) or default
            channel = f"[{channel_name}](<{channel_url}>)"
            video = f"[{name}]({url})"
            await webhook.send(
                msg.format(
                    name=name,
                    channel=channel,
                    channel_name=channel_name,
                    channel_url=channel_url,
                    url=url,
                    video=video,
                    link=url,
                ),
                allowed_mentions=AllowedMentions(
                    everyone=True, users=False, roles=True
                ),
            )


@app.before_server_start
async def before_server_start(app, loop):
    global mongo, db
    mongo = AsyncIOMotorClient(os.getenv("MONGO_URI"), io_loop=loop).strapbotrew
    await mongo.command({"ping": 1})  #  type: ignore
    db = mongo.YouTubeNews  # type: ignore
    app.ctx.mongo = mongo
    app.ctx.db = db
    await get_request_url()


@app.get("/")
async def ping(request: Request):
    return response.empty()


@app.route("/notify", methods=["GET", "POST"])
async def notify(request: Request):
    try:
        db: AgnosticCollection = app.ctx.db
        challenge = request.args.get("hub.challenge", "")
        if challenge:
            raise ReceivedChallenge(request.args)

        data = xmltodict.parse(request.body)
        feed = data["feed"]

        if "at:deleted-entry" in feed:
            channel_id = feed["at:deleted-entry"]["at:by"]["uri"].split("/")[-1]
        else:
            channel_id = feed["entry"]["yt:channelId"]

        entry = feed["entry"]
        url = entry["link"]["@href"]
        guilds = ((await db.find_one({"_id": channel_id})) or {}).get(  #  type: ignore
            "guilds", []
        )
        if not guilds:
            await request_pubsubhubbub(channel_id, False, False)
            await db.delete_one({"_id": channel_id})  # type: ignore
            return response.empty()

        tasks = []
        title = entry["title"]
        author = entry["author"]
        channel_name = author["name"]
        channel_url = author["uri"]
        for guild_id in guilds:
            gdb = mongo.YouTubeNewsGuilds  #  type: ignore
            gdata = await gdb.find_one({"_id": guild_id})
            tasks.append(
                send_new_video(
                    gdata["webhook_url"],
                    title,
                    url,
                    guild_id,
                    channel_id,
                    channel_name,
                    channel_url,
                    channel_id,
                )
            )

        await asyncio.gather(*tasks)

        return response.empty()
    except Exception as e:
        env = os.getenv("ERRORS_WEBHOOK_URL", None)
        if env != None:
            async with ClientSession() as session:
                wh = Webhook.from_url(env, session=session)
                files = []
                if request.args:
                    files.append(
                        File(
                            BytesIO(json.dumps(request.args, indent=4).encode()),
                            "args.json",
                        )
                    )

                if not isinstance(e, ReceivedChallenge):
                    files.append(File(BytesIO(format_exc().encode()), "traceback.py"))

                if request.body:
                    files.append(File(BytesIO(request.body), "body.xml"))
                await wh.send(f"{type(e).__name__}: {str(e)}", files=files)
        if isinstance(e, ReceivedChallenge):
            return response.text(e.challenge)
        else:
            raise


def get_envs():
    def _get_env_val(k: str) -> bool:
        env = os.getenv(k, "0")
        ret = False
        if env.isdigit():
            ret = bool(int(env))
        elif env.lower() in ["true", "false"]:
            ret = json.loads(env.lower())

        return ret

    debug = _get_env_val("SERVER_DEBUG")
    dev = _get_env_val("SERVER_DEV")
    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", 8080))
    request_url = os.getenv("SERVER_REQUEST_URL")
    return (host, port, debug, dev, request_url)


def create() -> sanic.Sanic:
    main(*get_envs(), False)
    return app


def main(
    host_: str,
    port_: int,
    debug: bool = False,
    dev: bool = False,
    request_url: Optional[str] = None,
    return_run: bool = True,
):
    global host, port
    host = host_
    port = port_
    if not request_url and host != "0.0.0.0":
        raise KeyError("An URL to receive requests is required.")

    if not request_url and host == "0.0.0.0" and return_run:
        hhw = os.getenv("HIDE_HOST_WARNING")
        if hhw == None:
            logger.warning(
                f"{Colors.YELLOW}"
                "You set host to 0.0.0.0, make sure you enabled port forwarding if"
                " you're self-hosting this in your home network. You can hide this"
                ' warning by setting the "HIDE_HOST_WARNING" environment variable '
                "to anything."
                f"{Colors.END}"
            )

    app.ctx.host = host
    app.ctx.port = port
    app.ctx.request_url = request_url

    if return_run:
        return create().run(host, port, dev=dev, debug=debug)


if __name__ in ["__main__", "__mp_main__"]:
    host, port, debug, dev, request_url = get_envs()
    main(host, port, debug, dev, request_url, __name__ != "__mp_main__")
