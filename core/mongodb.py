import secrets
import sys
import os
from datetime import datetime
from json import JSONDecodeError
from typing import Union, Optional

from discord import Member, DMChannel, TextChannel, Message

from aiohttp import ClientResponseError, ClientResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError

from logging import getLogger

logger = getLogger("Stockdroid Fans Bot")


class ApiClient:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.session = bot.session

    async def request(
        self,
        url: str,
        method: str = "GET",
        payload: dict = None,
        return_response: bool = False,
        headers: dict = None,
    ) -> Union[ClientResponse, dict, str]:
        """
        Makes a HTTP request.
        Parameters
        ----------
        url : str
            The destination URL of the request.
        method : str
            The HTTP method (POST, GET, PUT, DELETE, FETCH, etc.).
        payload : Dict[str, Any]
            The json payload to be sent along the request.
        return_response : bool
            Whether the `ClientResponse` object should be returned.
        headers : Dict[str, str]
            Additional headers to `headers`.
        Returns
        -------
        ClientResponse or Dict[str, Any] or List[Any] or str
            `ClientResponse` if `return_response` is `True`.
            `dict` if the returned data is a json object.
            `list` if the returned data is a json list.
            `str` if the returned data is not a valid json data,
            the raw response.
        """
        async with self.session.request(
            method, url, headers=headers, json=payload
        ) as resp:
            if return_response:
                return resp
            try:
                return await resp.json()
            except (JSONDecodeError, ClientResponseError):
                return await resp.text()

    def get_cog_partition(self, cog):
        return NotImplemented


class MongoDBClient(ApiClient):
    def __init__(self, bot):
        mongo_uri = os.getenv("MONGODB")
        if mongo_uri is None:
            logger.critical("A MongoDB is required.")
            raise RuntimeError

        try:
            db = AsyncIOMotorClient(mongo_uri).strapbot
        except ConfigurationError as e:
            logger.critical(
                "Your MondoDB connection string might be copied wrong, try copying it again. "
                "Otherwise check the following line:"
            )
            logger.critical(str(e))
            sys.exit(1)

        super().__init__(bot, db)

    async def setup_indexes(self):
        """Setup text indexes so we can use the $search operator"""
        coll = self.db.logs
        index_name = "messages.content_text_messages.author.name_text_key_text"

        index_info = await coll.index_information()

        # Backwards compatibility
        old_index = "messages.content_text_messages.author.name_text"
        if old_index in index_info:
            logger.info("Dropping old index: %s", old_index)
            await coll.drop_index(old_index)

        if index_name not in index_info:
            logger.info('Creating "text" index for logs collection.')
            logger.info("Name: %s", index_name)
            await coll.create_index(
                [
                    ("messages.content", "text"),
                    ("messages.author.name", "text"),
                    ("key", "text"),
                ]
            )
        logger.debug("Successfully configured and verified database indexes.")

    async def validate_database_connection(self):
        try:
            await self.db.command("buildinfo")
        except Exception as exc:
            logger.critical("Something went wrong while connecting to the database.")
            message = f"{type(exc).__name__}: {str(exc)}"
            logger.critical(message)

            if "ServerSelectionTimeoutError" in message:
                logger.critical(
                    "This may have been caused by not whitelisting "
                    "IPs correctly. Make sure to whitelist all "
                    "IPs (0.0.0.0/0) https://i.imgur.com/mILuQ5U.png"
                )

            if "OperationFailure" in message:
                logger.critical(
                    "This is due to having invalid credentials in your MONGO_URI. "
                    "Remember you need to substitute `<password>` with your actual password."
                )
                logger.critical(
                    "Be sure to URL encode your username and password (not the entire URL!!), "
                    "https://www.urlencoder.io/, if this issue persists, try changing your username and password "
                    "to only include alphanumeric characters, no symbols."
                    ""
                )

    def get_cog_partition(self, cog):
        cls_name = cog.__class__.__name__
        return self.db.cogs[cls_name]
