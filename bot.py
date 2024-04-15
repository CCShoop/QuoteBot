'''Written by Cael Shoop.'''

import os
import json
import random
from asyncio import Lock
from dotenv import load_dotenv
from datetime import datetime, timedelta
from discord import app_commands, Interaction, Intents, Client, TextChannel, Message, Guild, File
from discord.ext import tasks


def get_log_time():
    time = datetime.now().astimezone()
    output = ''
    if time.hour < 10:
        output += '0'
    output += f'{time.hour}:'
    if time.minute < 10:
        output += '0'
    output += f'{time.minute}:'
    if time.second < 10:
        output += '0'
    output += f'{time.second}>'
    return output


def main():
    class Quote():
        def __init__(self, quote_msg: Message):
            self.author = quote_msg.author
            self.content = quote_msg.content
            self.channel_id = quote_msg.channel.id
            self.date_time = quote_msg.created_at.astimezone().ctime()
            self.attachment_path = None
        
        def get_string(self, alternate_format = False):
            quote = ''
            if alternate_format:
                try:
                    quote = f'{self.author.mention}: "{self.content}"'
                except:
                    quote = f'{self.author.name}: "{self.content}"'
            else:
                if self.content != '':
                    quote = f'"{self.content}"\n'
                try:
                    quote += f'- {self.author.mention}, {self.date_time}, in <#{self.channel_id}>'
                except:
                    quote += f'- {self.author.name}, {self.date_time}, in <#{self.channel_id}>'
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
                print(f'{get_log_time()} Loading {self.FILENAME}')
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
                            print(f'{get_log_time()} Got guild id of {guild.id} and quote channel id of {quote_channel.id}')
                            self.quote_guilds.append(QuoteGuild(guild, quote_channel))
                    print(f'{get_log_time()} Successfully loaded {self.FILENAME}')
            else:
                print(f'{get_log_time()} File {self.FILENAME} does not exist')

        def write_json(self):
            data = {}
            for quote_guild in self.quote_guilds:
                data[quote_guild.guild.id] = {'quote_channel_id': quote_guild.quote_channel.id}
            json_data = json.dumps(data, indent=4)
            print(f'{get_log_time()} Writing {self.FILENAME}')
            with open(self.FILENAME, 'w+', encoding='utf-8') as file:
                file.write(json_data)

        async def setup_hook(self):
            await self.tree.sync()


    discord_token = os.getenv('DISCORD_TOKEN')
    client = QuoteClient(intents=Intents.all())

    @client.event
    async def on_ready():
        print(f'{get_log_time()} {client.user} has connected to Discord!')
        client.load_json()

    @client.tree.command(name='setchannel', description='Set a quote channel for a guild.')
    @app_commands.describe(channel_name='Name of the quote channel.')
    @app_commands.describe(channel_id='ID of the quote channel.')
    async def setchannel_command(interaction: Interaction, channel_name: str = None, channel_id: str = None):
        try:
            if channel_name:
                channel_name = channel_name.to_lower().replace(' ', '-')
                print(f'{get_log_time()} Setting quote channel for {interaction.guild.name} to provided NAME {channel_name}')
                for text_channel in interaction.guild.text_channels():
                    if text_channel.name == channel_name:
                        quote_channel = text_channel
                        break
                if not quote_channel:
                    raise Exception('No text channel found with provided channel name')
            elif channel_id:
                print(f'{get_log_time()} Setting quote channel for {interaction.guild.name} to provided ID {channel_id}')
                channel_id = int(channel_id)
                quote_channel = client.get_channel(channel_id)
                if not quote_channel:
                    raise Exception('No text channel found with provided channel id')
            else:
                print(f'{get_log_time()} Setting quote channel for {interaction.guild.name} to command\'s channel')
                quote_channel = interaction.channel
            client.quote_guilds.append(QuoteGuild(interaction.guild, quote_channel))
            client.write_json()
            await interaction.response.send_message(f'Successfully set quote channel for this guild to {quote_channel.name}.')
        except Exception as e:
            await interaction.response.send_message(f'Failed to set channel: {e}')
            print(f'{get_log_time()} Failed to set channel: {e}')

    @client.tree.command(name='quote', description='Quote the most recent or a specific Discord message.')
    @app_commands.describe(message_count='Number of messages to quote. Default is 1. WITHOUT message_id, it will quote the last (n) messages in the current channel. WITH message_id, it will quote the provided message as well as the following (n-1) messages.')
    @app_commands.describe(message_id='Discord message id to quote.')
    async def quote_command(interaction: Interaction, message_count: int = 1, message_id: str = None):
        try:
            quote_guild = client.get_quote_guild(interaction.guild)
            if not quote_guild:
                await interaction.response.send_message('There is no quote channel set for this guild! Please set one with /setchannel.')
                return
            quote_messages = []
            if message_id:
                message_id = int(message_id)
                first_quote_message = await interaction.channel.fetch_message(message_id)
                if not first_quote_message:
                    raise Exception('\'None\' return from fetch message(s) request.')
                quote_messages.append(first_quote_message)
                if message_count > 1:
                    async for message in first_quote_message.channel.history(after=first_quote_message, limit=message_count-1):
                        quote_messages.append(message)
            else:
                async for message in interaction.channel.history(limit=message_count):
                    quote_messages.append(message)
                quote_messages.reverse()
            if not quote_messages:
                raise Exception('\'None\' return from last message(s) request.')
            if quote_messages[0].reference:
                quote_messages.insert(0, await interaction.channel.fetch_message(quote_messages[0].reference.message_id))
            alternate_format = (len(quote_messages) != 1)
            if len(quote_messages) != 1:
                try:
                    await quote_guild.quote_channel.send(f'__In <#{interaction.channel.id}>, {quote_messages[0].created_at.astimezone().ctime()}:__')
                except Exception as e:
                    print(f'Error sending first message while referencing first message object: {e}\nTrying again referencing second message object...')
                    try:
                        await quote_guild.quote_channel.send(f'__In <#{interaction.channel.id}>, {quote_messages[1].created_at.astimezone().ctime()}:__')
                    except Exception as e:
                        print(f'Error referencing second message object: {e}')
                        await interaction.response.send_message(f'Error: {e}')
                        return
            for quote_message in quote_messages:
                quote = Quote(quote_message)
                quote_string = quote.get_string(alternate_format)
                if quote_message.attachments:
                    quote.attachment_path = f'{quote_message.id}.png'
                    with open(quote.attachment_path, 'wb') as file:
                        await quote_message.attachments[0].save(file)
                    await quote_guild.quote_channel.send(content=quote_string, file=File(quote.attachment_path))
                    try:
                        os.remove(quote.attachment_path)
                    except OSError as e:
                        print(f'{get_log_time()}> Error deleting {quote.attachment_path}: {e}')
                else:
                    await quote_guild.quote_channel.send(content=quote_string)
            await interaction.response.send_message(f'Quote successfully added to <#{quote_guild.quote_channel.id}>.')
            print(f'{get_log_time()} Successfully got last message(s) quote')
        except Exception as e:
            await interaction.response.send_message(f'Failed to quote message(s): {e}.')
            print(f'{get_log_time()} Failed to quote message(s): {e}')

    client.run(discord_token)


if __name__ == '__main__':
    load_dotenv()
    main()
