import dotenv
import os
import aiohttp
import asyncio
dotenv.load_dotenv()

from asyncspotify import Client, ClientCredentialsFlow
from asyncspotify.http import HTTP

loop = asyncio.get_event_loop()
client = Client(ClientCredentialsFlow(
   client_id=os.getenv("SPOTIFY_CLIENT_ID"),
   client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
))
client.http.loop = loop

async def main():
    await client.auth.authorize()
    pl = await client.get_playlist('2NdDBIGHUCu977yW5iKWQY')
    async for s in pl:
        print(s, s.uri)
    await client.close()

loop.run_until_complete(main())

print(client)