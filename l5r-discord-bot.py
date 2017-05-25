import discord
import logging
import json
import collections

import features.dice as dice

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='l5r-bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

client = discord.Client()

role_numbers_per_server = {}

with open('role_numbers.json', 'w+') as json_data:
    try:
        role_numbers_per_server = json.load(json_data)
    except json.decoder.JSONDecodeError:
        role_numbers_per_server = {}
with open('default_roles.json', 'w+') as json_data:
    try:
        default_roles = json.load(json_data)
    except json.decoder.JSONDecodeError:
        default_roles = {}


async def save_stats_to_file():
    with open('role_numbers.json', 'w') as outfile:
        json.dump(role_numbers_per_server, outfile)
        logger.info('Saved new role stats to file')

async def save_default_roles_to_file():
    with open('default_roles.json', 'w') as outfile:
        json.dump(role_numbers_per_server, outfile)
        logger.info('Saved default roles to file')


@client.event
async def on_ready():
    logger.info('Logged in as')
    logger.info(client.user.name)
    logger.info(client.user.id)
    logger.info('------')

    logger.info('Updating role statistics')
    for server in client.servers:
        stats = collections.Counter()
        for member in server.members:
            roles = [role.name for role in member.roles if role.name != '@everyone']
            stats.update(roles)
        role_numbers_per_server[server.name] = stats
    await save_stats_to_file()


@client.event
async def on_member_join(new_member):
    logger.info('A new member joined')
    try:
        roles = default_roles[new_member.server]
    except KeyError:
        logger.info('But there are no default roles set up!')
        return None
    client.add_roles(new_member, roles)
    logger.info('Added new roles to ' + new_member.name)

    role_numbers_per_server[new_member.server.name].update(roles)
    await save_stats_to_file()


@client.event
async def on_message(message):
    if message.content.startswith('!help'):
        logger.debug(str(message.author) + " asked for help!")
        help_text = "The Miya Herald has the following Emperor-granted powers: \n" + \
                    "\n" + \
                    "!help informs you about what he may do.  \n" + \
                    "\n" + \
                    "!clan <rolename> lets you swear allegiance to or leave a given clan. \n " + \
                    "!clan <rolename> default lets the admins set default roles that to apply to new members. \n \n" + \
                    "!clans tells you how many people are in each clan. \n \n" + \
                    "!roll is used to roll dice. \n" + \
                    "[] denotes optional elements, {} denotes 'pick one'. show_dice shows the individual dice " + \
                    "results. \n " + \
                    "The following formats are supported: \n \n" + \
                    "!roll XkY [{+-}Z} [TN##] [unskilled] [emphasis] [mastery] [show_dice] rolls X 10-sided " + \
                    "exploding dice and keeps the highest Y. \n" + \
                    "Unskilled can be set to prevent the dice from exploding, while Emphasis rerolls 1s. \n" + \
                    "Mastery allows the dice to explode on 9s and 10s. \n" + \
                    "Ex. !roll 6k3 TN20 or !roll 2k2 TN10 unskilled"
        await client.send_message(message.channel, help_text)

    if message.content.startswith('!clan') and message.content != '!clans':
        command = message.content.split(' ')[1:]
        if len(command) == 1:
            logger.info(message.author.name + ' wants to join or leave a clan!')
            role = discord.utils.find(lambda r: r.name == command[0], message.server.roles)
            if role is not None and role not in message.author.roles:
                try:
                    await client.add_roles(message.author, role)
                    role_numbers_per_server[message.server.name][role.name] += 1
                    await client.send_message(message.channel, 'Let it be known that ' + message.author.mention +
                                          ' joined the ' + role.name + ' clan!')
                except discord.errors.Forbidden:
                    await client.send_message(message.channel, 'How presumptuous! This is not a clan one can simply ' +
                                                               "join! *AKA you're not permitted to join this role*")
            elif role is not None and role in message.author.roles:
                await client.remove_roles(message.author, role)
                role_numbers_per_server[message.server.name][role.name] -= 1
                if role_numbers_per_server[message.server.name][role.name] == 0:
                    del(role_numbers_per_server[message.server.name][role.name])
                await client.send_message(message.channel, 'Let it be known that ' + message.author.mention +
                                          ' left the ' + role.name + ' clan!')
            else:
                await client.send_message(message.channel, 'Unfortunately, ' + message.author.mention +
                                          '-san, this clan is not listed in the Imperial Records...')
        elif len(command) == 2:
            if not message.author.server_permissions.manage_server:
                logger.warning(message.author.name + ' try to set default roles without permission!')
                await client.send_message(message.channel, 'You do not have permission to modify the default roles.')
                return None
            logger.info(message.author.name + ' wants to manage default roles.')
            if command[1] == 'default':
                role = discord.utils.find(lambda r: r.name == command[0], message.server.roles)
                try:
                    default_roles[message.server.name]
                except KeyError:
                    default_roles[message.server.name] = []
                if role.name in default_roles[message.server.name]:
                    default_roles[message.server.name].remove(role.name)
                    await save_default_roles_to_file()
                    await client.send_message(message.channel, role.name +
                                              ' has been removed from the default roles list.')
                else:
                    default_roles[message.server.name].append(role.name)
                    await save_default_roles_to_file()
                    await client.send_message(message.channel, role.name + ' has been added to the default roles list.')
            else:
                await client.send_message(message.channel, 'That is not a request I can fulfill. Perhaps you should ' +
                                                           'ask for !help first.')
    if message.content.startswith('!clans'):
        roles = role_numbers_per_server[message.server.name]
        response = ""
        for role, count in roles.items():
            response += role + ": " + str(count) + "\n"
        await client.send_message(message.channel, response)
    if message.content.startswith('!roll'):
        command = message.content.split(' ')[1:]
        if len(command) < 1:
            await client.send_message(message.channel,
                                      "4. Chosen by fair dice roll as the random number. "
                                      "If you wanted something else, perhaps look at !help")
        elif "k" in command[0]:
            roll, success = dice.roll_and_keep(command)
            await client.send_message(message.channel,
                                      message.author.mention + " rolled **" + str(roll) + "**! \n" + success)
        else:
            await client.send_message(message.channel,
                                      "Sorry, samurai-san, I didn't understand your request. \n"
                                      "!help should be informative for you.")


client.run('MzE3MjAwMjk5ODQ2NjY0MTky.DAgYmg.L9GPRhrc9HbaFEv2tyS5aG54FOY')