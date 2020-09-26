import json
import discord
from discord.ext import commands

class Vincy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.path = "core/vincyguild.json"
        self.guild = json.load(open(self.path))
        self.agree = self.guild["agree"]
    
    async def cog_check(self, ctx):
        if ctx.guild.id == self.guild["id"]:
            return True
        else:
            await ctx.send("This command works ONLY in Vincy's server.")
            return False
    
    @commands.command()
    @commands.has_role(595651372247154729)
    async def vincyrules(self, ctx):
        embed = discord.Embed(
            title="Regole del server",
            url="https://vincybot07.vincysuper07.cf",
            description="Questo server, come tutti gli altri, ha delle regole che __devono__ essere rispettate.",
            color=discord.Color.blurple(),
        ).add_field(
            name="REGOLA D'ORO!",
            value=f"Rispetta, accetta e sii gentile con tutti.\n"
            "Tagga <@&595651372247154729> se vieni molestato. Non reagire.",
            inline=False,
        ).add_field(
            name="1. Rispetta le regole di Discord",
            value="Per restare in questo server, dovrai seguire anche i [**Termini di Servizio**](http://discord.com/terms) e il [**regolamento**](http://discord.com/guidelines) di Discord!\nQuesto include:\n1. Devi avere **almeno** 13 anni per poter stare nel server.\n2. **NIENTE** NSFW."
        ).set_author(
            name="Vincysuper07",
            url="https://vincysuper07.cf",
            icon_url="https://cdn.discordapp.com/attachments/595327251579404298/682915766160588817/img2.png",
        ).add_field(
            name="2. È vietato alcun tipo di spam, flood, raid e altri tipi di spam.",
            value="Lo spam in questo server è proibito in questo server.\n"
            "Se qualcuno dovesse spammare, verrà kickato.\n"
            "Se qualcuno dovesse raidare, avete il consenso di spammare <@&595651372247154729>,\n"
            "noi prenderemo i provvedimenti necessari.",
            inline=False,
        ).add_field(
            name="3. È vietato insultare e bestemmiare.",
            value=f"Insulti, bestemmie, drammi e altre cose sono vietate in questo server.\n"
            "Se qualcuno dovesse bestemmiare oppure insultare, taggate <@&595651372247154729>.\n"
            "È consentito dire parolacce, però, solo fino a un certo punto.",
            inline=False,
        ).add_field(
            name="4. È vietato avere un nome impossibile da menzionare.",
            value="In questo server, i nomi devono essere **__tutti__ taggabili**. Quindi,\n"
            "un solo nome intaggabile, verrà cambiato in qualcos'altro.\n"
            "Se qualcuno dovesse rimettere il nome intaggabile, verrà avvertito, e,\n"
            "se necessario, verrà anche mutato!",
            inline=False,
        ).add_field(
            name="5. Non fare pubblicità.",
            value=f"La pubblicità al di fuori di <#595326853728960523> vale un warn, poi kick e ban!\n"
            "**La pubblicità in privato è __inclusa__!**",
            inline=False,
        ).add_field(
            name=f"6. Niente minimod nel server.",
            value=f"Lasciate gli <@&595651372247154729> fare il loro lavoro.",
            inline=False,
        ).add_field(
            name="Nota bene:",
            value=f"•Tutte le regole elencate qui sopra, **valgono __anche__ in chat privata**, quindi,\n"
            "se qualcuno dovesse violare una o più regole nella chat privata, taggate <@&595651372247154729>,\n"
            "provvederemo noi a tutto.\n"
            "•Violazione di una regola: __Warn__\n"
            "4 Warn in 2 settimane: **Mute per __2 giorni__**\n"
            "5 Warn in 2 settimane: **__Ban__**!\n"
            "•Gli <@&595651372247154729> possono bannarti senza warn in qualsiasi momento!",
            inline=False,
        ).set_footer(text="Buona permanenza nel server!")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_role(595651372247154729)
    async def vincyagree(self, ctx):
        msg = await ctx.send(
            embed=discord.Embed(
                title="Per poter stare nel server...",
                description=(
                    f"Leggi le <#641268747667111938>, dopodichè aggiungi la reazione {self.agree['emoji']} qui sotto. "
                    f"Se non funziona la reazione, scrivi `{self.agree['to_send']}`, se non funziona nemmeno quello, tagga "
                    f"<@&595651372247154729>, ti aggiungeremo noi il ruolo manualmente. Un qualsiasi messaggio che non è `{self.agree['to_send']}` "
                    "o <@&595651372247154729> equivale a un kick. 5 kick = ban!"
                ),
                color=discord.Color.blurple()
            )
        )
        self.agree["message_id"] = msg.id
        json.dump(self.guild, open(self.path, "w"), indent=4)
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        print(f"A reaction was added to a message:\nMessage ID: {payload.message_id} - {self.agree['message_id']}\nEmoji: {payload.emoji} - {self.agree['emoji']}\nChannel ID: {payload.channel_id} - {self.agree['channel_id']}") 
        if payload.message_id == int(self.agree["message_id"]):
            if str(payload.emoji) == str(self.agree["emoji"]):
                await payload.member.add_roles(self.bot.get_role(595318972178497547), reason="Ha accettato le regole")
                await self.bot.get_channel(595327311012823045).send(f"**{payload.member}** ha accettato le regole.")
            else:
                await self.bot.http.remove_reaction(int(self.agree["channel_id"]), int(self.agree["message_id"]), self.agree["emoji"], payload.user_id)
            
            
            
        
        
        
        
        
        
        

def setup(bot):
    bot.add_cog(Vincy(bot))
