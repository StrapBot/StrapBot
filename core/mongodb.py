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


class MongoDB:
    def __init__(self, bot):
        self.bot = bot
        mongo_uri = os.getenv("MONGODB")
        if mongo_uri is None:
            self.bot.logger.critical("A MongoDB is required.")
            raise RuntimeError

        try:
            self.db = AsyncIOMotorClient(mongo_uri).strapbot
        except ConfigurationError as e:
            self.bot.logger.critical(
                "Your MondoDB connection string might be copied wrong, try copying it again. "
                "Otherwise check the following line:"
            )
            self.bot.logger.critical(str(e))
            bot.loop.create_task(bot.close())

            raise

    async def setup_indexes(self):
        """Setup text indexes so we can use the $search operator"""
        coll = self.db.logs
        index_name = "messages.content_text_messages.author.name_text_key_text"

        index_info = await coll.index_information()

        # Backwards compatibility
        old_index = "messages.content_text_messages.author.name_text"
        if old_index in index_info:
            self.bot.logger.info("Dropping old index: %s", old_index)
            await coll.drop_index(old_index)

        if index_name not in index_info:
            self.bot.logger.info('Creating "text" index for logs collection.')
            self.bot.logger.info("Name: %s", index_name)
            await coll.create_index(
                [
                    ("messages.content", "text"),
                    ("messages.author.name", "text"),
                    ("key", "text"),
                ]
            )
        self.bot.logger.debug("Successfully configured and verified database indexes.")

    async def validate_database_connection(self):
        try:
            await self.db.command("buildinfo")
        except Exception as exc:
            self.bot.logger.critical(
                "Something went wrong while connecting to the database."
            )
            message = f"{type(exc).__name__}: {str(exc)}"
            self.bot.logger.critical(message)

            if "ServerSelectionTimeoutError" in message:
                self.bot.logger.critical(
                    "This may have been caused by not whitelisting "
                    "IPs correctly. Make sure to whitelist all "
                    "IPs (0.0.0.0/0) https://i.imgur.com/mILuQ5U.png"
                )

            if "OperationFailure" in message:
                self.bot.logger.critical(
                    "This is due to having invalid credentials in your MONGO_URI. "
                    "Remember you need to substitute `<password>` with your actual password."
                )
                self.bot.logger.critical(
                    "Be sure to URL encode your username and password (not the entire URL!!), "
                    "https://www.urlencoder.io/, if this issue persists, try changing your username and password "
                    "to only include alphanumeric characters, no symbols."
                    ""
                )

    def get_cog_partition(self, cog):
        cls_name = cog.__class__.__name__
        return self.db.cogs[cls_name]
