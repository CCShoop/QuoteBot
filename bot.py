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
        async def __init__(self, quote_msg: Message):
            self.author = quote_msg.author
            self.content = quote_msg.content
            self.datetime = quote_msg.created_at().astimezone()
            if quote_msg.attachments:
                self.attachment_path = f'{quote_msg.id}.png'
                with open(self.attachment_path, 'wb') as file:
                    await message.attachments[0].save(file)
            else:
                self.attachment_path = None
        
        def get_string(self):
            quote = ''
            if self.content != '':
                quote = f'"{self.content}"\n'
            quote += f'- {self.author.name}, {self.datetime.ctime()}'
            return quote

    class QuoteGuild():
        def __init__(self, guild: Guild, quote_channel: TextChannel):
            self.guild = guild
            self.quote_channel = quote_channel

    class SchedulerClient(Client):
        def __init__(self, intents):
            super(SchedulerClient, self).__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)
            self.FILENAME = 'info.json'
            self.quote_guilds = []
            self.load_json()

        def get_quote_guild(self, guild: Guild):
            for quote_guild in self.quote_guilds:
                if guild.id == quote_guild.guild.id:
                    return quote_guild
            return None

        def load_json(self):
            if os.path.exists(self.FILENAME):
                print(f'{get_log_time()} Reading {self.FILENAME}')
                with open(self.FILENAME, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    for firstField, secondField in data.items():
                        guild = self.get_guild(int(firstField))
                        quote_channel = self.get_channel(int(secondField['quote_channel_id']))
                        print(f'{get_log_time()} Got guild id of {guild.id} and quote channel id of {quote_channel.id}')
                        self.quote_guilds.append(QuoteGuild(guild, quote_channel))
                    print(f'{get_log_time()} Successfully loaded {self.FILENAME}')

        def write_json(self):
            data = {}
            for guild in self.quote_guilds:
                data[guild.id] = {'quote_channel_id': guild.quote_channel.id}
            json_data = json.dumps(data, indent=4)
            print(f'{get_log_time()} Writing {self.FILENAME}')
            with open(self.FILENAME, 'w+', encoding='utf-8') as file:
                file.write(json_data)

        async def setup_hook(self):
            await self.tree.sync()


    discord_token = os.getenv('DISCORD_TOKEN')
    client = SchedulerClient(intents=Intents.all())

    @client.event
    async def on_ready():
        print(f'{get_log_time()} {client.user} has connected to Discord!')

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
    @app_commands.describe(message_id='Discord message id to quote.')
    async def quote_command(interaction: Interaction, message_id: str = None):
        try:
            message_id = int(message_id)
            quote_guild = client.get_quote_guild(interaction.guild)
            if not quote_guild:
                raise Exception('\'None\' return from quote guild request.')
            if message_id:
                quote_message = quote_guild.quote_channel.last_message()
                if not quote_message:
                    raise Exception('\'None\' return from last message request.')
            else:
                quote_message = quote_guild.quote_channel.get_partial_message(message_id)
                if not quote_message:
                    raise Exception('\'None\' return from partial message request.')
            quote = await Quote()
            quote_string = quote.get_string()
            if quote.attachment_path:
                await quote_guild.quote_channel.send(content=quote_string, file=quote.attachment_path)
            else:
                await quote_guild.quote_channel.send(content=quote_string)
            try:
                os.remove(quote.attachment_path)
            except OSError as e:
                print(f'{get_log_time()}> Error deleting {quote.attachment_path}: {e}')
            await interaction.response.send_message(f'Quote successfully added to {quote_guild.quote_channel.name}.')
            print(f'{get_log_time()} Successfully got last message quote')
        except Exception as e:
            await interaction.response.send_message(f'Failed to quote message: {e}.')
            print(f'{get_log_time()} Failed to quote message: {e}')

    client.run(discord_token)


if __name__ == '__main__':
    load_dotenv()
    main()
