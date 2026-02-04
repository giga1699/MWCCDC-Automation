import os
from dotenv import load_dotenv
import ccdczulip
import ccdcnextcloud
import ccdcmantis
import re
import json
import csv
import requests
import ccdchelpers
import string
import random

# Set this to provide debugging output
debug = False

# Should we check Zulip group memberships? Probably not since bots can't look at that specific endpoint. Will fail safe if there's an issue
checkZulipGroupMembership = True

# Defaults
authentikMasterBlackGroup="08a6f2b2-5566-433e-8413-52e08804dcaa"
authentikMasterGreenGroup="07f57ea0-1f10-4981-949a-2d873a9cf49c"
authentikMasterRedGroup="12a2505b-dad5-4f90-97ad-285e0f00b7a1"
teamPassCSV="teampasswords.csv"
teamNameRegex="team\d+[a-i]"
teamUserDomainName="@comp.ccdc.events"
zulipOperationsChannel="operations"
zulipOperationsTopic="automation-messages"
zulipOperationsGroup="Black Team"
zulipBlueGroupRegex="Team \d+"
zulipBlueChannelRegex="Team \d+ Chat"
zulipBlueAnnounceTopic="automation-messages"
zulipOrangeChannelRegex="Team \d+ Orange"
zulipGreenChannelRegex="Team \d+ Support"
compTeamInfoTXT="compTeamInfo.txt"

# You may need to change the below according to your own Zulip install. Unfortunately bots can't get groups :(
defaultZulipGroups = {
    "Red Team": 30,
    "Black Team": 37,
    "Green Team": 41,
    "Team 01": 61,
    "Team 02": 65,
    "Team 03": 70,
    "Team 04": 74,
    "Team 05": 78,
    "Team 06": 82,
    "Team 07": 86,
    "Team 08": 90,
    "Team 09": 94,
    "Team 10": 98,
    "Team 11": 102,
    "Team 12": 106,
    "Team 13": 110,
    "Team 14": 114,
    "Team 15": 118,
    "Team 16": 122,
    "Team 17": 126,
    "Team 18": 130,
    "Team 19": 134,
    "Team 20": 138,
    "White Team": 208,
    "Orange Team": 294,
    "State Directors": 471,
}

# Main dict for CCDC competition information
compTeamInfo = {}

# Load .env file if it exists
if os.path.isfile(".env"):
    load_dotenv()

# Check if the environment variable DEBUG is set. If so, provide debugging output
if os.getenv('DEBUG'):
    debug = True

# Overwrite defaults, if defined in env var
if os.getenv('authentikMasterBlackGroup'):
    teamPassCSV=os.getenv('authentikMasterBlackGroup')
if os.getenv('authentikMasterGreenGroup'):
    teamPassCSV=os.getenv('authentikMasterGreenGroup')
if os.getenv('teamPassCSV'):
    teamPassCSV=os.getenv('teamPassCSV')
if os.getenv('teamNameRegex'):
    teamNameRegex=os.getenv('teamNameRegex')
if os.getenv('teamUserDomainName'):
    teamUserDomainName=os.getenv('teamUserDomainName')
if os.getenv('zulipOperationsChannel'):
    zulipOperationsChannel=os.getenv('zulipOperationsChannel')
if os.getenv('zulipOperationsTopic'):
    zulipOperationsChannel=os.getenv('zulipOperationsTopic')
if os.getenv('zulipOperationsGroup'):
    zulipOperationsGroup=os.getenv('zulipOperationsGroup')
if os.getenv('zulipBlueGroupRegex'):
    zulipBlueGroupRegex=os.getenv('zulipBlueGroupRegex')
if os.getenv('zulipBlueChannelRegex'):
    zulipBlueChannelRegex=os.getenv('zulipBlueChannelRegex')
if os.getenv('zulipBlueAnnounceTopic'):
    zulipBlueAnnounceTopic=os.getenv('zulipBlueAnnounceTopic')
if os.getenv('zulipOrangeChannelRegex'):
    zulipOrangeChannelRegex=os.getenv('zulipOrangeChannelRegex')
if os.getenv('zulipGreenChannelRegex'):
    zulipGreenChannelRegex=os.getenv('zulipGreenChannelRegex')

# Output default values if debugging enabled
if debug:
    print(f'Default values set for this run...\n\nTeam Name Regex: {teamNameRegex}\r\nzulipOperationsChannel: {zulipOperationsChannel}\r\nzulipOperationsTopic: {zulipOperationsTopic}')

# Create the Zulip connection
zulip = ccdczulip.CCDCZulip(os.getenv('zulipEmail'), os.getenv('zulipToken'), debug=debug)
zulipAdmin = ccdczulip.CCDCZulip(os.getenv('zulipAdminEmail'), os.getenv('zulipAdminToken'), debug=debug)

# Create the Nextcloud connection
nextcloud = ccdcnextcloud.CCDCNextcloud(os.getenv('ncAppUser'), os.getenv('ncAppPass'), os.getenv('ncDomain'), debug=debug)

# Create the Mantis connection
mantis = ccdcmantis.CCDCMantis(os.getenv('mantisToken'), os.getenv('mantisDomain'), debug=debug)

# authentik header and domain
authentikHeaders = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
  'Authorization': 'Bearer ' + os.getenv('authentikToken')
}
authentikDomain = os.getenv('authDomain')

# Let's start closing out everything that was previously setup
zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "Trying to sync support (green/black) users from auth to Zulip/Mantis...")

# Get Zulip channels
zulipChannels = zulipAdmin.getAllChannels()['streams']
if debug:
    print(zulipChannels)

# Get Mantis projects
mantisProjects = mantis.getAllProjects()['projects']
if debug:
    print(mantisProjects)

# Get a list of black team usernames from authentik
payload = json.dumps({
    "include_children": True,
})
response = requests.request("GET", f'https://{authentikDomain}/api/v3/core/groups/{authentikMasterBlackGroup}/', headers=authentikHeaders, data=payload)
if debug:
    print(response.status_code, response.text)

if response.status_code != 200:
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*Black Team* **ERROR**: Couldn\'t get a list of black team users using group pk {authentikMasterBlackGroup}')
    exit(-1)

for userObj in response.json()['users_obj']:
    if debug:
        print(userObj['username'], userObj['name'], userObj['email'])
    
    # Try to create Zulip user
    try:
        randomPass = ''.join(random.sample(string.ascii_letters + string.digits, 30))
        zulip.createUser(userObj['email'], randomPass, userObj['name'])
    except Exception as ex:
        if not re.search('Email is already in use', str(ex)):
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t create Zulip user with email {userObj["email"]}.\r\nException:\r\n```\r\n{ex}\r\n```')

    zulipUserID = zulip.getUserIDByEmail(userObj['email'])
    if zulipUserID:
        try:
            zulipAdmin.addUserToGroup(zulipUserID, defaultZulipGroups['Black Team'])
        except Exception as ex:
            if not re.search('User \d+ is already a member of this group', str(ex)):
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t add Zulip user with email {userObj["email"]} to "Black Team" group.\r\nException:\r\n```\r\n{ex}\r\n```')
    
    try:
        for channel in zulipChannels:
            if re.match(zulipOperationsChannel, channel['name']) and zulipUserID:
                zulipAdmin.subscribeUserToChannel(zulipUserID, channel['name'])
    except Exception as ex:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding zulip ID {zulipUserID} to black team channel(s).\r\nException:```\r\n{ex}\r\n```')
    
    # Try to create Mantis user
    try:
        mantis.createUser(userObj['username'], "manager")
    except Exception as ex:
        if not re.search('That username is already being used', str(ex)):
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding Mantis user {userObj["username"]}.\r\nException:```\r\n{ex}\r\n```')
    
    for project in mantisProjects:
        try:
            mantis.addUserToProject(userObj['username'], project['id'], 'manager')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding Mantis user {userObj["username"]} to project {project["id"]}.\r\nException:```\r\n{ex}\r\n```')

# Get a list of green team usernames from authentik
payload = json.dumps({
    "include_children": True,
})
response = requests.request("GET", f'https://{authentikDomain}/api/v3/core/groups/{authentikMasterGreenGroup}/', headers=authentikHeaders, data=payload)
if debug:
    print(response.status_code, response.text)

if response.status_code != 200:
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*Black Team* **ERROR**: Couldn\'t get a list of green team users using group pk {authentikMasterGreenGroup}')
    exit(-1)

for userObj in response.json()['users_obj']:
    if debug:
        print(userObj['username'], userObj['name'], userObj['email'])
    
    # Try to create Zulip user
    try:
        randomPass = ''.join(random.sample(string.ascii_letters + string.digits, 30))
        zulip.createUser(userObj['email'], randomPass, userObj['name'])
    except Exception as ex:
        if not re.search('Email is already in use', str(ex)):
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t create Zulip user with email {userObj["email"]}.\r\nException:\r\n```\r\n{ex}\r\n```')

    zulipUserID = zulip.getUserIDByEmail(userObj['email'])
    if zulipUserID:
        try:
            zulipAdmin.addUserToGroup(zulipUserID, defaultZulipGroups['Green Team'])
        except Exception as ex:
            if not re.search('User \d+ is already a member of this group', str(ex)):
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t add Zulip user with email {userObj["email"]} to "Green Team" group.\r\nException:\r\n```\r\n{ex}\r\n```')
    
    try:
        for channel in zulipChannels:
            if (re.match(zulipGreenChannelRegex, channel['name']) or re.match("green-team-internal", channel['name'])) and zulipUserID:
                zulipAdmin.subscribeUserToChannel(zulipUserID, channel['name'])
    except Exception as ex:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding zulip ID {zulipUserID} to green team channel(s).\r\nException:```\r\n{ex}\r\n```')
    
    # Try to create Mantis user
    try:
        mantis.createUser(userObj['username'], "manager")
    except Exception as ex:
        if not re.search('That username is already being used', str(ex)):
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding Mantis user {userObj["username"]}.\r\nException:```\r\n{ex}\r\n```')
    
    for project in mantisProjects:
        try:
            mantis.addUserToProject(userObj['username'], project['id'], 'manager')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding Mantis user {userObj["username"]} to project {project["id"]}.\r\nException:```\r\n{ex}\r\n```')

## RED TEAM
# Get a list of green team usernames from authentik
payload = json.dumps({
    "include_children": True,
})
response = requests.request("GET", f'https://{authentikDomain}/api/v3/core/groups/{authentikMasterRedGroup}/', headers=authentikHeaders, data=payload)
if debug:
    print(response.status_code, response.text)

if response.status_code != 200:
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*Black Team* **ERROR**: Couldn\'t get a list of red team users using group pk {authentikMasterRedGroup}')
    exit(-1)

for userObj in response.json()['users_obj']:
    if debug:
        print(userObj['username'], userObj['name'], userObj['email'])
    
    # Try to create Zulip user
    try:
        randomPass = ''.join(random.sample(string.ascii_letters + string.digits, 30))
        zulip.createUser(userObj['email'], randomPass, userObj['name'])
    except Exception as ex:
        if not re.search('Email is already in use', str(ex)):
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t create Zulip user with email {userObj["email"]}.\r\nException:\r\n```\r\n{ex}\r\n```')

    zulipUserID = zulip.getUserIDByEmail(userObj['email'])
    if zulipUserID:
        try:
            zulipAdmin.addUserToGroup(zulipUserID, defaultZulipGroups['Red Team'])
        except Exception as ex:
            if not re.search('User \d+ is already a member of this group', str(ex)):
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t add Zulip user with email {userObj["email"]} to "Red Team" group.\r\nException:\r\n```\r\n{ex}\r\n```')
    
    try:
        for channel in zulipChannels:
            if (re.match("red-team", channel['name'])) and zulipUserID:
                zulipAdmin.subscribeUserToChannel(zulipUserID, channel['name'])
    except Exception as ex:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error adding zulip ID {zulipUserID} to red team channel(s).\r\nException:```\r\n{ex}\r\n```')

zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "Support user sync complete!")