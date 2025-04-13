# bot.py
import os
import random
import requests

from discord.ext import commands, tasks
import discord 
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
GROUP_NAME = os.getenv('GROUP_NAME')
CHANNEL_IDS_STRING = os.getenv('CHANNEL_IDS')

CHANNEL_IDS = set()

if CHANNEL_IDS_STRING:
    id_list = CHANNEL_IDS_STRING.split(',')
    CHANNEL_IDS = {int(id_str.strip()) for id_str in id_list if id_str.strip()}
    

# Set up Google Sheets access
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("api-project-911197427573-cf160699dfad.json", scope)
gc = gspread.authorize(credentials)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!',intents=intents)

def in_channel_ids():
    """A decorator to check if a command is used in a specific channel by ID."""
    async def predicate(ctx):
        return ctx.channel.id in CHANNEL_IDS
    
    return commands.check(predicate)

class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__()
        
    async def send_bot_help(self, mapping):
        """Help for all commands."""
        if self.context.channel.id not in CHANNEL_IDS:  # Replace with your desired channel ID
            return await self.context.send("This command can only be used in a specific channel.")
        
        embed = discord.Embed(title="Bot Commands", description="List of available commands. For more information on any specific one, please type !help followed by the command. (E.g. !help sync):", color=discord.Color.dark_red())

        # Define command order explicitly
        command_order = ['sync', 'a', 's', 'name_change','d','clog','clog_s']  # Add your priority commands here

        # Fetch bot commands
        all_commands = {cmd.name: cmd for cmd in self.context.bot.commands}  # Dictionary of all commands

        # Add ordered commands first
        added_commands = set()
        for cmd_name in command_order:
            command = all_commands.get(cmd_name)
            if command:
                embed.add_field(name=f"!{command.name}", value=command.help or "No description", inline=False)
                added_commands.add(cmd_name)  # Track added commands

        # Add remaining commands that weren't in command_order
        for command in self.context.bot.commands:
            if command.name not in added_commands:
                embed.add_field(name=f"!{command.name}", value=command.help or "No description", inline=False)

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        """Help for a specific command with argument descriptions."""
        if self.context.channel.id not in CHANNEL_IDS:  # Replace with your desired channel ID
            return await self.context.send("This command can only be used in a specific channel.")
        
        embed = discord.Embed(title=f"!{command.name}", description=command.help or "No description", color=discord.Color.darker_grey())

        if command.clean_params:
            for param in command.clean_params:
                description = self.get_argument_description(command.name, param)
                embed.add_field(name=f"{param}", value=description or "No description given", inline=False)
        else:
            embed.add_field(name="Arguments", value="This command takes no arguments.", inline=False)

        await self.get_destination().send(embed=embed)

    def get_argument_description(self, command_name, param):
        """Define argument descriptions for each command and parameter here."""
        descriptions = {
            "a": {
                "code": "The column on the spreadsheet to update.",
                "rsn": "The RuneScape name of the member.",
            },
            "s" : {
                "code": "The column on the spreadsheet to update.",
                "rsn": "The RuneScape name of the member.",
            },
            'name_change': {
                'old_name': 'The previous Runescape name of the clan member. Use double quotes for best results.',
                'new_name': 'The new Runescape name of the clan member. Make sure you spell it right and use double quotes for best results.'
            },
            'd': {
                'code': 'The column in the diaries page to update. You can find a list in the "Diary Info" section of the spreadsheet.',
                'rsn': 'The Runescape name of the member.'
            },
            'clog': {
                'num': 'The amount of Collections Logged that the clan member currently has.',
                'rsn': 'The Runescape name of the member.'
            },
            'clog_s': {
                'num': 'The amount of Collections Logged that the clan member currently has.',
                'rsn': 'The Runescape name of the member.'
            },
            'donate': {
                'num' : 'The amount donated.',
                'rsn' : 'The rsn of the donater'
            }
            
        }
        return descriptions.get(command_name, {}).get(param)

# Set the custom help command
bot.help_command = CustomHelpCommand()

def update_gs(code,rsn,operator,num):
    if (code == 'diary'):
        return 6
    elif (code in ['points2','determined_rank', 'time_in_clan','placeholder1','placeholder2','placeholder3','placeholder4','discord_name','active']):
        return 7
    sheet = gc.open("Respair Ranking Sheet").worksheet("Data")
    cell = sheet.find(rsn.lower())
    max_1 = ['ca_elite','ca_master','ca_gm','inferno','quiver','blorva']
    #Invalid rsn
    if not(isinstance(cell,gspread.cell.Cell)): return 0 
    row = sheet.row_values(cell.row)
    headers = sheet.row_values(1)
    if code in headers:
        col_index = headers.index(code.lower())
        #Only let users update column Q onward manually.
        if (col_index < 16): return 7
        current_value = row[col_index]
        try:
            if operator == '+':
                current_value = int(current_value)
                if (current_value == 1) and (code in max_1):
                    #Can't increment a value beyond 1 in the designated categories
                    return 5
                else:
                    new_value = current_value + num
                    sheet.update_cell(cell.row, col_index + 1, new_value)
                    #Success!
                    return 4
            elif operator == '-':
                if (int(current_value)) == 0:
                    #Can't decrement a 0 value
                    return 3
                else:
                    sheet.update_cell(cell.row, col_index + 1, int(current_value) - num)
                    #Success!
                    return 4
        except:
            #Unknown? Number does not exist.
            return 2
    #Invalid Column Code    
    else: return 1
    return
    
def get_osrs_clan_data():
    url = f'https://api.wiseoldman.net/v2/groups/{GROUP_NAME}'
    
    # Make the request to the API
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        return response.json()
    else:
        # If the request failed, print the status code and return None
        print(f"Error: Unable to fetch data (Status Code: {response.status_code})")
        return None    

def get_osrs_player_data(rsn):
    url = f'https://api.wiseoldman.net/v2/players/{rsn}'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        # If the request failed, print the status code and return None
        print(f"Error: Unable to fetch data (Status Code: {response.status_code})")
        return None
    
def getCombinedRaidKcAndClogs(rsn):
    raids = ['tombs_of_amascut', 'tombs_of_amascut_expert', 'theatre_of_blood', 'theatre_of_blood_hard_mode', 'chambers_of_xeric', 'chambers_of_xeric_challenge_mode']
    pd = get_osrs_player_data(rsn)
    bosses = pd['latestSnapshot']['data']['bosses']
    kc = 0
    for key, value in bosses.items():
        kc_standardize = lambda x: max(x,0)
        if key in raids:
            kc += kc_standardize(value['kills'])
    clogs = pd['latestSnapshot']['data']['activities']['collections_logged']['score']
    return [kc,clogs]

def fetch_raw_wom():
    data = get_osrs_clan_data()
    player_dict = {}
    for member in data['memberships']:
        name = member['player']['username']
        joinDate = member['createdAt']
        ehb = member['player']['ehb']
        exp = member['player']['exp']
        role = member['role']
        crkc = []
        try:
            crkc = getCombinedRaidKcAndClogs(name)
        except:
            crkc = []
        player_dict[name] = [joinDate,role,ehb,exp] + crkc
    return player_dict

@bot.command(name='a', help='Used to add points to a member\'s rank score.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def add(ctx, code, *, rsn: str):
    res = update_gs(code, rsn, '+', 1)
    promo_check = check_for_promotion(rsn)
    if (res == 0):
        await ctx.send(f'{rsn} is not a valid rsn.')
    elif (res == 1):
        await ctx.send(f'{code} is not a valid reason code.')
    elif (res == 2):
        await ctx.send(f'An unknown error occurred. Make sure the current score is an integer.')
    elif (res == 3):
        await ctx.send(f'{rsn}\'s {code} value can\'t go any lower!')
    elif (res == 4):
        if (promo_check[0] == 4):
            await ctx.send(f'Success! {rsn}\'s {code} score has increased! They are due for a promotion to {promo_check[3]}.')
        else:
            await ctx.send(f'Success! {rsn}\'s {code} score has increased!')
    elif (res == 5):
        await ctx.send(f'Failure. {code} is already capped at 1. It can\'t go any higher!')
    elif (res == 6):
        await ctx.send(f'To update a diary, use the !d command.')
    elif (res == 7):
        await ctx.send(f'That field can\'t be altered manually')
        
@bot.command(name='s', help='Used to subtract points from a member\'s rank score.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def add(ctx, code, *, rsn: str):
    res = update_gs(code, rsn, '-', 1)
    if (res == 0):
        await ctx.send(f'{rsn} is not a valid rsn.')
    elif (res == 1):
        await ctx.send(f'{code} is not a valid reason code.')
    elif (res == 2):
        await ctx.send(f'An unknown error occurred. Make sure the current score is an integer.')
    elif (res == 3):
        await ctx.send(f'{rsn}\'s {code} value can\'t go any lower!')
    elif (res == 4):
        await ctx.send(f'Success! {rsn}\'s {code} score has decreased... :(.')
    elif (res == 5):
        await ctx.send(f'Failure. {code} is already capped at 1. It can\'t go any higher!')
    elif (res == 6):
        await ctx.send(f'To update a diary, use the !d command.')
    elif (res == 7):
        await ctx.send(f'That field can\'t be altered manually')
        
@bot.command(name='donate', help='Used to add points to a member\'s donation score. Max of 10 at a time.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def add(ctx, num: int, *, rsn: str):
    # if (not isinstance(int,num)): 
    #     await ctx.send('Please enter an integer between 1 and 10.')
    #     return
    if (num < -10 or num > 10): 
        await ctx.send(f'The maximum amount of point-eligible donations is currently 10m per month. {num} is outside those parameters.')
        return
    res = update_gs('donate', rsn, '+', num)
    promo_check = check_for_promotion(rsn)
    if (res == 0):
        await ctx.send(f'{rsn} is not a valid rsn.')
    elif (res == 1):
        await ctx.send(f'\'donate\' is not a valid reason code.')
    elif (res == 2):
        await ctx.send(f'An unknown error occurred. Make sure the current score is an integer.')
    elif (res == 3):
        await ctx.send(f'{rsn}\'s \'donate\' value can\'t go any lower!')
    elif (res == 4):
        if (promo_check[0] == 4):
            await ctx.send(f'Success! {rsn}\'s \'donate\' score has increased! They are due for a promotion to {promo_check[3]}.')
        else:
            await ctx.send(f'Success! {rsn}\'s \'donate\' score has increased!')
    elif (res == 5):
        await ctx.send(f'Failure. \'donate\' is already capped at 1. It can\'t go any higher!')
    elif (res == 6):
        await ctx.send(f'To update a diary, use the !d command.')
    elif (res == 7):
        await ctx.send(f'That field can\'t be altered manually')    

@bot.command(name='sync', help='Syncs the member list of the spreadsheet with WOM.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def sync(ctx):
    sheet = gc.open("Respair Ranking Sheet").worksheet("Raw WOM")
    wom_data = fetch_raw_wom()
    # Custom header
    custom_header = ['name', 'joinDate', 'role', 'ehb', 'exp', 'combined_raid_kc','clogs']
    # Update header row
    sheet.update("A1", [custom_header])
    print("Header updated in the specific worksheet!")
    rows = []
    for key, values in wom_data.items():
        row = [key] + values  # First element is the key, followed by the list of values
        rows.append(row)
    # # Write rows starting at A2
    sheet.update("A2", rows)
    response = requests.post('https://script.google.com/macros/s/AKfycbwMsyTjFi7p55UBc9hqgZfFZ60quVs1Cp4VTNeU-tpDs0jHigacBnqi2EM1DOwrn1NG/exec')
    if response.status_code == 200:
        await ctx.send("Data updated successfully!")
    else:
        await ctx.send(f"Failed to update data. Error: {response.text}")
        
    # await ctx.send('Sync complete! Just kidding this isn\'t set up yet.')

@bot.command(name='name_change', help='Updates the rsn of a member. Use double quotes (\"\") if either name has spaces!')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def update_rsn(ctx, old_name: str, new_name: str):
    sheet = gc.open("Respair Ranking Sheet").worksheet("Data")
    cell = sheet.find(old_name.lower())
    #Invalid rsn
    if not(isinstance(cell,gspread.cell.Cell)): 
        await ctx.send(f'The username: {old_name} could not be found. Please ensure you\'re correctly enclosing names in double quotes (\"\") if they contain spaces.') 
    else:
        sheet.update_cell(cell.row, cell.col, new_name)
        await ctx.send(f'Success. {old_name}\'s rsn has been updated to {new_name}!')

@bot.command(name='d', help='Used to mark completion of Respair Diaries.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def update_rsn(ctx, code, *, rsn: str):
    sheet = gc.open("Respair Ranking Sheet").worksheet("Diaries")
    cell = sheet.find(rsn.lower())
    #Invalid rsn
    if not(isinstance(cell,gspread.cell.Cell)): 
        await ctx.send(f'Rsn: {rsn} could not be found.')
    else: 
        headers = sheet.row_values(1)
        if code in headers:
            col_index = headers.index(code.lower())
            sheet.update_cell(cell.row, col_index + 1, 1)
            await ctx.send(f'Big gz to {rsn} for completing the {code} diary!')
        else:
            await ctx.send(f'Code: {code} could not be found.')
            
@bot.command(name='clog_s', help='Used to set a member\'s STARTING clog # if below 500.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def set_start_clog(ctx, num: int, *, rsn: str):
    sheet = gc.open("Respair Ranking Sheet").worksheet("Data")
    cell = sheet.find(rsn.lower())
    #Invalid rsn
    if not(isinstance(cell,gspread.cell.Cell)): 
        await ctx.send(f'Rsn: {rsn} could not be found.')
    elif (num > 0): 
        sheet.update_cell(cell.row, 8, num)
        await ctx.send(f'{rsn}\'s start clog # has been updated to {num}.')
    else:
        await ctx.send(f'Don\'t do {rsn} dirty like that. Give them a positive score.')

@bot.command(name='clog', help='Used to set a member\'s CURRENT clog # if below 500.')
@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def set_start_clog(ctx, num: int, *, rsn: str):
    sheet = gc.open("Respair Ranking Sheet").worksheet("Data")
    cell = sheet.find(rsn.lower())
    #Invalid rsn
    if not(isinstance(cell,gspread.cell.Cell)): 
        await ctx.send(f'Rsn: {rsn} could not be found.')
    elif (num > 0): 
        sheet.update_cell(cell.row, 12, num)
        await ctx.send(f'{rsn}\'s start clog # has been updated to {num}.')
    else:
        await ctx.send(f'Don\'t do {rsn} dirty like that. Give them a positive score.')

def check_for_promotion(rsn):
    omit = ['owner','deputy_owner','coordinator','beast','goblin','legend','anchor','moderator','councillor']
    trial_period = 30
    sheet = gc.open("Respair Ranking Sheet").worksheet("Data")
    cell = sheet.find(rsn.lower())
    #Invalid rsn
    if not(isinstance(cell,gspread.cell.Cell)):
        return [0,rsn,'','',0]
    row = sheet.row_values(cell.row)
    
    current_rank = str(row[2]).strip().lower()  # Make sure to strip and lower the current rank
    determined_rank = str(row[45]).strip().lower()  # Ensure consistent formatting

    #Member still in trial period
    trial_check = int(row[42])
   
    if (trial_check < trial_period): 
        return [1,rsn,current_rank,determined_rank,trial_period-trial_check]
    #Member's rank is outside the ranking system
    elif (current_rank in omit):
        return [2,rsn,current_rank,determined_rank,0]
    #Correct rank matches current rank
    elif (current_rank == determined_rank):
        return [3,rsn,current_rank,determined_rank,0]
    #Rank needs to be updated
    else:
        return [4,rsn,current_rank,determined_rank,0]

@bot.command(name='promo', help='Check whether or not a player is due a promotion. Can be used by anyone in the server!')
#@commands.has_any_role('Moderator','Owners')
@in_channel_ids()
async def test(ctx, *, rsn: str): 
    res = check_for_promotion(rsn)
    print(str(res))
    if (res[0] == 0):
        await ctx.send(f'Sorry, {res[1]} wasn\'t found. Please check the spelling and try again.')
    elif (res[0] == 1):
        await ctx.send(f'{res[1]} is still in their trial period. Try again in {res[4]} more days!')
    elif (res[0] == 2):
        await ctx.send(f'{res[1]}\'s rank is assigned outside of this process.')
    elif (res[0] == 3):
        await ctx.send(f'Sorry, {res[1]} isn\'t due for a promotion yet. Keep on truckin\'')
    elif (res[0] == 4):
        await ctx.send(f'{res[1]} is due for a promotion to {res[3]}!')
    else:
        await ctx.send(f'An unforeseen error occurred. Please contact a mod or try again after a few minutes.')
        
    
# @bot.command(name='gstest')
# async def lookup(ctx, rsn: str, code: str):
#     """Looks up a username and retrieves corresponding data from the sheet."""
    
#     try:
#         # Find the cell that contains the username in the first column
#         cell = sheet.find(rsn)
#         print(f'{type(cell)}')
#         if isinstance(cell,gspread.cell.Cell): print('True')
#         else: print('False')
        
#         # Get the row of the found cell
#         row = sheet.row_values(cell.row)
        
#          # Get all column headers (assumes the first row contains headers)
#         headers = sheet.row_values(1)  # First row for headers
        
#         # Find the index of the requested column (by its name)
#         if code in headers:
#             col_index = headers.index(code) + 1  # Adding 1 since sheet columns are 1-indexed
#             result = row[col_index - 1]  # Get the value from the specified column (indexing starts from 0)
#             await ctx.send(f"The value for {rsn} in the '{code}' column is: {result}")
#         else:
#             await ctx.send(f"Column '{code}' not found in the sheet.")
    
#     except gspread.exceptions.CellNotFound:
#         await ctx.send(f"Sorry, no data found for username: {rsn}")
        
#     except Exception as e:
#         # Catch any other unexpected errors and print them
#         await ctx.send(f"An unexpected error occurred: {str(e)}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('Please use one of the approved channels and ensure that you\
 have the appropriate rank for the comnmand you\'re trying to run.')
        
# @bot.event
# async def on_ready():
#     print(f'Logged in as {bot.user}')
#     sync_task.start()

# @tasks.loop(time=datetime.time(hour=0, minute=17))  # Runs daily at 12:17 AM
# async def sync_task():
#     print("Running scheduled sync command...")  # Optional log for visibility

#     # Perform the sync
#     await bot.tree.sync()

#     # Send a message in the specified channel
#     # channel = bot.get_channel(CHANNEL_IDS)
#     # if channel:
#     #     await channel.send("✅ `/sync` command has been successfully executed!")

#     print("Sync command executed and confirmation sent.")
    
# @bot.command(name='test', help='Tester method to test things')
# @commands.has_any_role('Moderator','Owners')
# @in_channel_ids()
# async def update_rsn(ctx):
#     member = ctx.author
#     guild = ctx.guild
#     TARGET_ROLE_ID=1358543820005839116
#     # 1. Find the target role object in the current guild using its ID
#     target_role = guild.get_role(TARGET_ROLE_ID)

#     if target_role is None:
#         await ctx.send(f"Sorry, the role I'm supposed to assign couldn't be found on this server. Please notify an admin.")
#         print(f"Error: Role ID {TARGET_ROLE_ID} not found in guild '{guild.name}' ({guild.id})")
#         return

#     # 2. Check if the member already has the role
#     if target_role in member.roles:
#         await ctx.send(f"{member.mention}, you already have the '{target_role.name}' role!")
#         return

#     # 3. Check if the bot has permissions and is high enough in the hierarchy
#     bot_member = guild.me # The bot's member object in this guild
#     if not bot_member.guild_permissions.manage_roles:
#         await ctx.send("I don't have the `Manage Roles` permission required to assign roles.")
#         print(f"Permission Error: Bot lacks 'Manage Roles' in guild '{guild.name}' ({guild.id}).")
#         return

#     if bot_member.top_role <= target_role:
#         # Bot's highest role is lower than or equal to the target role
#         await ctx.send(f"I cannot assign the '{target_role.name}' role because my highest role ('{bot_member.top_role.name}') needs to be higher than it in the server's role list.")
#         print(f"Hierarchy Error: Bot role '{bot_member.top_role.name}' not higher than target '{target_role.name}' in '{guild.name}'.")
#         return

#     # 4. Attempt to add the role
#     try:
#         await member.add_roles(target_role, reason=f"Assigned via !getrole command by {member.name}")
#         await ctx.send(f"Successfully assigned the '{target_role.name}' role to {member.mention}!")
#         print(f"Assigned role '{target_role.name}' to {member.name} ({member.id}) in '{guild.name}'.")

#     except discord.Forbidden:
#         # Should ideally be caught by the checks above, but handles edge cases/race conditions
#         await ctx.send("It seems I encountered a permissions issue while trying to assign the role. Please double-check my permissions and role hierarchy.")
#         print(f"Forbidden Error during add_roles for {member.name} in '{guild.name}'.")
#     except discord.HTTPException as e:
#         # Handles other potential Discord API errors (e.g., rate limits)
#         await ctx.send(f"An error occurred while communicating with Discord: {e}")
#         print(f"HTTPException during add_roles for {member.name} in '{guild.name}': {e}")
#     except Exception as e:
#         # Catch any other unexpected errors
#         await ctx.send("An unexpected error occurred while assigning the role.")
#         print(f"Unexpected Error during add_roles for {member.name} in '{guild.name}': {e}")



bot.run(TOKEN)