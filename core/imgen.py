import os

from discord import File
from io import BytesIO

class UnauthorizedError(Exception):
    pass

class DankMemerImgen:
    """this is just the Dank Memer API but on StrapBot"""

    def __init__(self, bot):
        self.bot = bot
        self.TOKEN = os.getenv("DANKMEMER_AUTHORIZATION", None)
        self.URL = os.getenv("DANKMEMER_URL", "https://dankmemer.services")
        self.headers = {"Authorization": self.TOKEN}

    def request(self, thing):
        """Make an HTTP request and get the video/image."""
        async def something(fmt="png", **params):
            if self.TOKEN == None:
                raise UnauthorizedError(
                    "I can't run it without Authorization token.\n"
                    "If you are the owner of the bot, please submit the bot "
                    f"at {self.URL}/request and wait for it to be approved."
                )

            async with self.bot.session.post(f"{self.URL}/api/{thing}", json=params, headers=self.headers) as request:
                response = await request.content.read()
                if not fmt in ["text", "plain", "plaintext"]:
                    byte = BytesIO(response)
                    file = File(byte, filename=f"file.{fmt}")
                else:
                    file = response.decode("UTF-8")

            return file

        return something

    def __getattr__(self, item):
        return self.request(item)

    async def crab(self, fmt="mp4", **params):
        return await self.request("crab")(fmt, **params)

    async def kowalski(self, fmt="gif", **params):
        return await self.request("kowalski")(fmt, **params)

    async def letmein(self, fmt="mp4", **params):
        return await self.request("letmein")(fmt, **params)