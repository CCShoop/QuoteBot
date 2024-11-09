'''Written by Cael Shoop.'''

import os
import json
import logging
from dotenv import load_dotenv
from discord import app_commands, Interaction, Intents, Client, TextChannel, Message, Guild, File


load_dotenv()

# Logger setup
logger = logging.getLogger("Quote Bot")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='[Quote Bot] [%(asctime)s] [%(levelname)s\t] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = logging.FileHandler('quotebot.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class Quote():
    def __init__(self, quote_msg: Message):
        self.guild = quote_msg.guild
        self.author = quote_msg.author
        self.content = quote_msg.content
        self.channel_id = quote_msg.channel.id
        self.message_id = quote_msg.id
        self.date_time = quote_msg.created_at.astimezone().ctime()
        self.attachment_path = None

    def get_string(self, alternate_format=False):
        quote = ''
        if alternate_format:
            if self.author.nick:
                quote += f'**{self.author.nick}:** '
            else:
                quote += f'**{self.author.name}:** '
            if self.content != '':
                quote += f'"{self.content}"\n'
            else:
                quote += '\n'
        else:
            if self.content != '':
                quote += f'"{self.content}"\n'
            if self.author.nick:
                quote += f'**- {self.author.nick}, {self.date_time}, in <#{self.channel_id}>**\n'
            else:
                quote += f'**- {self.author.name}, {self.date_time}, in <#{self.channel_id}>**\n'
        return quote


class QuoteGuild():
    def __init__(self, guild: Guild, quote_channel: TextChannel):
        self.guild = guild
        self.quote_channel = quote_channel


class QuoteClient(Client):
    def __init__(self, intents):
        super(QuoteClient, self).__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.FILENAME = 'info.json'
        self.quote_guilds = []

    def get_quote_guild(self, guild: Guild):
        for quote_guild in self.quote_guilds:
            if guild.id == quote_guild.guild.id:
                return quote_guild
        return None

    def load_json(self):
        if os.path.exists(self.FILENAME):
            logger.info(f'Loading {self.FILENAME}')
            with open(self.FILENAME, 'r', encoding='utf-8') as file:
                data = json.load(file)
                for firstField, secondField in data.items():
                    found = False
                    for quote_guild in self.quote_guilds:
                        if quote_guild.guild.id == int(firstField):
                            found = True
                            break
                    if not found:
                        guild = self.get_guild(int(firstField))
                        quote_channel = self.get_channel(int(secondField['quote_channel_id']))
                        if not guild:
                            raise Exception('Failed to get guild from id in json')
                        if not quote_channel:
                            raise Exception('Failed to get quote channel from id in json')
                        logger.info(f'Got guild id of {guild.id} and quote channel id of {quote_channel.id}')
                        self.quote_guilds.append(QuoteGuild(guild, quote_channel))
                logger.info(f'Successfully loaded {self.FILENAME}')
        else:
            logger.info(f'File {self.FILENAME} does not exist')

    def write_json(self):
        data = {}
        for quote_guild in self.quote_guilds:
            data[quote_guild.guild.id] = {'quote_channel_id': quote_guild.quote_channel.id}
        json_data = json.dumps(data, indent=4)
        logger.info(f'Writing {self.FILENAME}')
        with open(self.FILENAME, 'w+', encoding='utf-8') as file:
            file.write(json_data)

    async def setup_hook(self):
        await self.tree.sync()


discord_token = os.getenv('DISCORD_TOKEN')
client = QuoteClient(intents=Intents.all())


@client.event
async def on_ready():
    logger.info(f'{client.user} has connected to Discord!')
    client.load_json()


@client.tree.command(name='setchannel', description='Set a quote channel for a guild.')
@app_commands.describe(channel_name='Name of the quote channel.')
@app_commands.describe(channel_id='ID of the quote channel.')
async def setchannel_command(interaction: Interaction, channel_name: str = None, channel_id: str = None):
    try:
        if channel_name:
            channel_name = channel_name.to_lower().replace(' ', '-')
            logger.info(f'Setting quote channel for {interaction.guild.name} to provided NAME {channel_name}')
            for text_channel in interaction.guild.text_channels():
                if text_channel.name == channel_name:
                    quote_channel = text_channel
                    break
            if not quote_channel:
                raise Exception('No text channel found with provided channel name')
        elif channel_id:
            logger.info(f'Setting quote channel for {interaction.guild.name} to provided ID {channel_id}')
            channel_id = int(channel_id)
            quote_channel = client.get_channel(channel_id)
            if not quote_channel:
                raise Exception('No text channel found with provided channel id')
        else:
            logger.info(f'Setting quote channel for {interaction.guild.name} to command\'s channel')
            quote_channel = interaction.channel
        client.quote_guilds.append(QuoteGuild(interaction.guild, quote_channel))
        client.write_json()
        await interaction.response.send_message(f'Successfully set quote channel for this guild to {quote_channel.name}.', ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f'Failed to set channel: {e}', ephemeral=True)
        logger.info(f'Failed to set channel: {e}')


@client.tree.command(name='quote', description='Quote the most recent or a specific Discord message.')
@app_commands.describe(message_count='Number of messages to quote. Default is 1. WITHOUT message_id, it will quote the last (n) messages in the current channel. WITH message_id, it will quote the provided message as well as the following (n-1) messages.')
@app_commands.describe(message_id='Discord message id to quote.')
async def quote_command(interaction: Interaction, message_count: int = 1, message_id: str = None):
    try:
        quote_guild = client.get_quote_guild(interaction.guild)
        if not quote_guild:
            await interaction.response.send_message('There is no quote channel set for this guild! Please set one with /setchannel.', ephemeral=True)
            return
        quote_messages = []
        # Grab specific message(s)
        if message_id:
            message_id = int(message_id)
            first_quote_message = await interaction.channel.fetch_message(message_id)
            if not first_quote_message:
                await interaction.response.send_message(f'Error: failed to fetch message with id {message_id}.', ephemeral=True)
                raise Exception('\'None\' return from fetch message(s) request.')
            quote_messages.append(first_quote_message)
            if message_count > 1:
                async for message in first_quote_message.channel.history(after=first_quote_message, limit=message_count - 1):
                    quote_messages.append(message)
        # Grab last message(s)
        else:
            async for message in interaction.channel.history(limit=message_count):
                quote_messages.append(message)
            quote_messages.reverse()
        # Check that there are messages
        if not quote_messages:
            await interaction.response.send_message('Error: Failed to fetch message(s).', ephemeral=True)
            raise Exception('No quote messages found.')
        await interaction.response.defer(ephemeral=True)
        # Grab message that was replied to by first message
        if quote_messages[0].reference:
            quote_messages.insert(0, await interaction.channel.fetch_message(quote_messages[0].reference.message_id))
        alternate_format = (len(quote_messages) != 1)
        if len(quote_messages) != 1:
            try:
                await quote_guild.quote_channel.send(f'**https://discord.com/channels/{quote_messages[0].guild.id}/{quote_messages[0].channel.id}/{quote_messages[0].message.id}, {quote_messages[0].created_at.astimezone().ctime()}:**')
            except Exception as e:
                logger.error(f'Error sending first message while referencing first message object: {e}')
                logger.error('Trying again, referencing second message object...')
                try:
                    await quote_guild.quote_channel.send(f'**https://discord.com/channels/{quote_messages[1].guild.id}/{quote_messages[1].channel.id}/{quote_messages[1].message.id}, {quote_messages[1].created_at.astimezone().ctime()}:**')
                except Exception as e:
                    logger.error(f'Error referencing second message object: {e}')
                    await interaction.followup.send(f'Error: {e}')
                    return
        # Send quote messages in quote channel
        quote_string = ''
        files = []
        for quote_message in quote_messages:
            quote = Quote(quote_message)
            quote_string += quote.get_string(alternate_format)
            if quote_message.attachments:
                counter = 0
                for attachment in quote_message.attachments:
                    quote.attachment_path = f'{quote_message.id}_{counter}.png'
                    with open(quote.attachment_path, 'wb') as file:
                        await attachment.save(file)
                    files.append(File(quote.attachment_path))
                    try:
                        os.remove(quote.attachment_path)
                    except OSError as e:
                        logger.error(f'Error deleting {quote.attachment_path}: {e}')
                    counter += 1
        quote = None
        if len(files) > 0:
            quote = await quote_guild.quote_channel.send(content=quote_string, files=files)
        elif quote_string != '':
            quote = await quote_guild.quote_channel.send(content=quote_string)
        else:
            await interaction.followup.send('Empty quote.')
            return
        quote_id = ''
        if quote is not None:
            quote_id = f"{quote.id}"
        await interaction.followup.send(f'Quote successfully added! https://discord.com/channels/{quote_guild.guild.id}/{quote_guild.quote_channel.id}/{quote_id}')
        logger.info('Successfully quoted message(s)')
    except Exception as e:
        await interaction.followup.send(f'Failed to quote message(s): {e}.')
        logger.error(f'Failed to quote message(s): {e}')

client.run(discord_token)
