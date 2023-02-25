"""Server for receiving requests from Google's PubSubHubbub."""

import os
import sanic
import json
import xmltodict
import asyncio
from aiohttp import ClientSession
from sanic import Request, response
from sanic.log import logger, error_logger, server_logger, Colors
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticClient, AgnosticCollection
from discord import Webhook, NotFound, File
from io import BytesIO
from typing import Optional

load_dotenv()
app = sanic.Sanic("strapbot_server")
mongo: Optional[AgnosticClient] = None
db: Optional[AgnosticCollection] = None


async def get_request_url():
    req_url = app.ctx.request_url
    if not req_url and app.ctx.host == "0.0.0.0":
        async with ClientSession() as session:
            async with session.get("http://ifconfig.me/ip") as resp:
                req_url = (
                    f"http://{(await resp.content.read()).decode()}:{app.ctx.port}"
                )
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
    channel_name: str,
    channel_url: str,
    channel_id: str,
):
    db: AgnosticCollection = app.ctx.db
    async with ClientSession() as session:
        try:
            webhook = await Webhook.from_url(webhook_url, session=session).fetch()
        except NotFound:
            webhooks = (
                (await db.find_one({"_id": channel_id})) or {}  #  type: ignore
            ).get("webhooks", [])
            webhooks.remove(webhook_url)
            if not webhooks:
                await request_pubsubhubbub(channel_id, False, False)
                await db.delete_one({"_id": channel_id})  # type: ignore
            else:
                await db.update_one({"_id": channel_id}, {"$set": {"webhooks": webhooks}})  # type: ignore
        else:
            # cfgdb: AgnosticCollection = mongo.Configurations # type: ignore
            # guild_config = await cfgdb.find_one({"_id": webhook.guild_id}) # type: ignore
            # msg = guild_config["youtube_message"]
            msg = f"sera. [{channel_name}](<{channel_url}>) ha pubblicato un nuovo coso™: {url}"
            await webhook.send(msg)


@app.before_server_start
async def before_server_start(app, loop):
    global mongo, db
    mongo = AsyncIOMotorClient(os.getenv("MONGO_URI"), io_loop=loop).strapbotrew
    await mongo.command({"ping": 1})  #  type: ignore
    db = mongo.YouTubeNews  # type: ignore
    app.ctx.mongo = mongo
    app.ctx.db = db


@app.get("/")
async def ping(request: Request):
    return response.empty()


@app.route("/notify", methods=["GET", "POST"])
async def notify(request: Request):
    try:
        db: AgnosticCollection = app.ctx.db
        challenge = request.args.get("hub.challenge", "")
        if challenge:
            return response.text(challenge, 200)

        data = xmltodict.parse(request.body)
        feed = data["feed"]

        if "at:deleted-entry" in feed:
            channel_id = feed["at:deleted-entry"]["at:by"]["uri"].split("/")[-1]
        else:
            channel_id = feed["entry"]["yt:channelId"]

        entry = feed["entry"]
        url = entry["link"]["@href"]
        webhooks = (
            (await db.find_one({"_id": channel_id})) or {}  #  type: ignore
        ).get("webhooks", [])
        if not webhooks:
            await request_pubsubhubbub(channel_id, False, False)
            await db.delete_one({"_id": channel_id})  # type: ignore
            return response.empty()

        tasks = []
        title = entry["title"]
        author = entry["author"]
        channel_name = author["name"]
        channel_url = author["uri"]
        for wh in webhooks:
            tasks.append(
                send_new_video(wh, title, url, channel_name, channel_url, channel_id)
            )

        await asyncio.gather(*tasks)

        return response.empty()
    except Exception as e:
        env = os.getenv("ERRORS_WEBHOOK_URL", None)
        if env != None:
            async with ClientSession() as session:
                wh = Webhook.from_url(env, session=session)
                await wh.send(
                    f"{type(e).__name__}: {str(e)}",
                    file=File(BytesIO(request.body), "body.xml"),
                )
        raise


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
        return app.run(host, port, dev=dev, debug=debug)


if __name__ in ["__main__", "__mp_main__"]:

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
    main(host, port, debug, dev, request_url, __name__ != "__mp_main__")
