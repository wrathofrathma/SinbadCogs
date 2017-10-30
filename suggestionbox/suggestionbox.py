import os
import asyncio  # noqa: F401
import discord
import logging
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils import checks

class SuggestionBox:
    """custom cog for a configureable suggestion box"""

    __author__ = "mikeshardmind"
    __version__ = "1.4.1"

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json('data/suggestionbox/settings.json')
        for s in self.settings:
            self.settings[s]['usercache'] = []

    def save_json(self):
        dataIO.save_json("data/suggestionbox/settings.json", self.settings)

    @commands.group(name="setsuggest", pass_context=True, no_pm=True)
    async def setsuggest(self, ctx):
        """configuration settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    def initial_config(self, server_id):
        """makes an entry for the server, defaults to turned off"""

        if server_id not in self.settings:
            self.settings[server_id] = {'inactive': True,
                                        'output': [],
                                        'cleanup': False,
                                        'usercache': [],
                                        'multiout': False
                                        }
            self.save_json()

    @checks.admin_or_permissions(Manage_server=True)
    @setsuggest.command(name="fixcache", pass_context=True, no_pm=True)
    async def fix_cache(self, ctx):
        """use this if the bot gets stuck not recording your response"""
        self.initial_config(ctx.message.server.id)
        self.settings[server.id]['usercache'] = []
        self.save_json()

    @checks.admin_or_permissions(Manage_server=True)
    @setsuggest.command(name="output", pass_context=True, no_pm=True)
    async def setoutput(self, ctx, chan: discord.Channel):
        """sets the output channel(s)"""
        server = ctx.message.server
        if server.id not in self.settings:
            self.initial_config(server.id)
        if server != chan.server:
            return await self.bot.say("Stop trying to break this")
        if chan.type != discord.ChannelType.text:
            return await self.bot.say("That isn't a text channel")
        if chan.id in self.settings[server.id]['output']:
            return await self.bot.say("Channel already set as output")

        if self.settings[server.id]['multiout']:
            self.settings[server.id]['output'].append(chan.id)
            self.save_json()
            return await self.bot.say("Channel added to output list")
        else:
            self.settings[server.id]['output'] = [chan.id]
            self.save_json()
            return await self.bot.say("Channel set as output")

    @checks.admin_or_permissions(Manage_server=True)
    @setsuggest.command(name="toggleactive", pass_context=True, no_pm=True)
    async def suggest_toggle(self, ctx):
        """Toggles whether the suggestion box is enabled or not"""
        server = ctx.message.server
        if server.id not in self.settings:
            self.initial_config(server.id)
        self.settings[server.id]['inactive'] = \
            not self.settings[server.id]['inactive']
        self.save_json()
        if self.settings[server.id]['inactive']:
            await self.bot.say("Suggestions disabled.")
        else:
            await self.bot.say("Suggestions enabled.")

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="suggest", pass_context=True)
    async def makesuggestion(self, ctx):
        "make a suggestion by following the prompts"
        author = ctx.message.author
        server = ctx.message.server

        if server.id not in self.settings:
            return await self.bot.say("Suggestion submissions have not been "
                                      "configured for this server.")
        if self.settings[server.id]['inactive']:
            return await self.bot.say("Suggestion submission is not currently "
                                      "enabled on this server.")

        if author.id in self.settings[server.id]['usercache']:
            return await self.bot.say("Finish making your prior sugggestion "
                                      "before making an additional one")

        await self.bot.say("I will message you to collect your suggestion.")
        self.settings[server.id]['usercache'].append(author.id)
        self.save_json()
        dm = await self.bot.send_message(author,
                                         "Please respond to this message"
                                         "with your suggestion.\nYour "
                                         "suggestion should be a single "
                                         "message")
        message = await self.bot.wait_for_message(channel=dm.channel,
                                                  author=author, timeout=120)

        if message is None:
            await self.bot.send_message(author,
                                        "I can't wait forever, "
                                        "try again when ready")
            self.settings[server.id]['usercache'].remove(author.id)
            self.save_json()
        else:
            await self.send_suggest(message, server)

            await self.bot.send_message(author, "Your suggestion was "
                                        "submitted.")

    async def send_suggest(self, message, server, user: discord.Member=None):

        author = server.get_member(message.author.id)
        suggestion = message.clean_content
        avatar = author.avatar_url if author.avatar \
            else author.default_avatar_url
        
        if not user:
            user = author
	#This is where we configure the suggestion-box look. 
        em = discord.Embed(description=suggestion, timestamp=message.timestamp,
                           color=discord.Color.purple())    
        em.set_author(name='Suggestion from {0.display_name}'.format(author),
                      icon_url=avatar)

        name = str(user)

        if user.avatar_url:
            em.set_author(name=name, url=user.avatar_url)
            em.set_thumbnail(url=user.avatar_url)
        else:
            em.set_author(name=name)

	#end configuration of the box aesthetics.

        for output in self.settings[server.id]['output']:
            where = server.get_channel(output)
            if where is not None:
                message = await self.bot.send_message(where, embed=em)
                await self.bot.add_reaction(message, "👍")
                await self.bot.add_reaction(message, "👎")

        self.settings[server.id]['usercache'].remove(author.id)
        self.save_json()

    #Let's start setting up our response
    @checks.admin_or_permissions(Manage_server=True)
    @commands.command(name="respond", pass_context=True, no_pm=True)
    async def accept(self, ctx):
        server = ctx.message.server 
        author = server.get_member(ctx.message.author.id)

    	#Let's split the string into smol pieces. Command structure should be like .accept suggestion_message_id response
        response_split = ctx.message.content.split()
        
        #Test if there is a message ID
        if(len(response_split) < 2):
            await self.bot.send_message(ctx.message.channel, "Try adding a suggestion ID you cunt")
            return
        suggest_id = response_split[1]

        #Test if there is an accept/deny value
        if(len(response_split) < 3):
            await self.bot.send_message(ctx.message.channel, "Accepting or denying? The fuck man you gotta let someone know.")
            return
        #Test if the accept/deny value is actually fucking useful
        if(response_split[2]!="accept" and response_split[2]!="deny" and response_split[2]!="meh"):
            await self.bot.send_message(ctx.message.channel, "Do you know how to type? You need to accept/deny")
#            await self.bot.send_message(ctx.message.channel, response_split[2])

            return
            
        #Test if there is a response
        if(len(response_split) < 4):
            await self.bot.send_message(ctx.message.channel, "Motherfucker, try adding a response")
            return

        #Test if the suggestion message_id is valid. Let's try to keep it consistent with multiple output channels.
        for output in self.settings[server.id]['output']:
            where = server.get_channel(output)
            if(where is not None):
                #This try/except is to catch for when bitches don't use a suggestion ID. It'll throw an HTTPException: 400 Bad Request.
                try:
                    suggestion = await self.bot.get_message(where,suggest_id)
                except discord.errors.HTTPException:
                    await self.bot.send_message(ctx.message.channel, "You probably input an invalid message ID and broke the bot you cuck")
                    return
                if(suggestion.content!=None):
                    break
        #I'm not actually sure this will ever get triggered, because I think discord.errors.HTTPException gets thrown if the message isn't found period. As does discord.errors.NotFound. 
        if(suggestion == None):
            await self.bot.send_message(ctx.message.channel, "Couldn't find suggestion message")
            return

        #discord.Message.embed contains a single nested dictionary object at element 0. This contains multiple other dictionaries for each element. 
        #Let's use this to configure our response.
        em = discord.Embed(
                            type="rich",
                            description=suggestion.embeds[0]['description'], 
                            timestamp=ctx.message.timestamp, 
                            color=discord.Color.red())
        if(response_split[2]=="accept"):
            em.color=discord.Color.green()
        elif(response_split[2]=="deny"):
            em.color=discord.Color.red()
        else:
            em.color=discord.Color.light_grey()

        sauthor = server.get_member_named(suggestion.embeds[0]['author']['name'])
        avatar = sauthor.avatar_url if sauthor.avatar \
            else sauthor.default_avatar_url
        em.set_author(name=format(sauthor))
        em.set_thumbnail(url=avatar)
        em.add_field(name='Response by: {0.display_name}'.format(author), value=" ".join(response_split[3:]))
        #End response configuration

        for output in self.settings[server.id]['output']:
            where = server.get_channel(output)
            if where is not None:
                message = await self.bot.send_message(where, embed=em) 
                await self.bot.add_reaction(message, "👍")
                await self.bot.add_reaction(message, "👎")
        await self.bot.delete_message(message=suggestion)

        	
def check_folder():
    f = 'data/suggestionbox'
    if not os.path.exists(f):
        os.makedirs(f)


def check_file():
    f = 'data/suggestionbox/settings.json'
    if dataIO.is_valid_json(f) is False:
        dataIO.save_json(f, {})


def setup(bot):
    check_folder()
    check_file()
    n = SuggestionBox(bot)
    bot.add_cog(n)
