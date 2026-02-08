import os
from dotenv import load_dotenv
import ccdczulip
import ccdcnextcloud
import ccdcmantis
import re
import json
import csv
import requests
import sys
import ccdchelpers

# Set this to provide debugging output
debug = False

# Should we check Zulip group memberships? Probably not since bots can't look at that specific endpoint. Will fail safe if there's an issue
checkZulipGroupMembership = True

# Defaults
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
## Should contain team numbers
### Users (username)
#### Zulip
##### email, id
#### Authentik
##### pk
### Zulip Channels
#### Channel name: ID
### Folders (nextcloud)
#### Folder name: folderID
### Groups
#### Zulip {name: id}
#### Nextcloud [list]
### URLs
#### Nextcloud-Upload-Share
#### Nextcloud-Upload-Share-Short
compTeamInfo = {}

# Load .env file if it exists
if os.path.isfile(".env"):
    load_dotenv()

# Check if the environment variable DEBUG is set. If so, provide debugging output
if os.getenv('DEBUG'):
    debug = True

# Overwrite defaults, if defined in env var
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
if os.getenv('compTeamInfoTXT'):
    compTeamInfoTXT=os.getenv('compTeamInfoTXT')

# Output default values if debugging enabled
if debug:
    print(f'Default values set for this run...\n\nTeam Name Regex: {teamNameRegex}\r\nzulipOperationsChannel: {zulipOperationsChannel}\r\nzulipOperationsTopic: {zulipOperationsTopic}')

# Create the Zulip connection
zulip = ccdczulip.CCDCZulip(os.getenv('zulipEmail'), os.getenv('zulipToken'), debug=debug)

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

# Check if we have a sys argument passed to download the compTeamInfo.txt file; To start out, support downloading the copy sent to zulip ops chat
downloadCompTeamInfo = False
for arg in sys.argv[1:]:
    if "=" in arg:
        key, val = arg.split("=", 1)
        if key == "compTeamInfoURL":
            if debug:
                print(f'Going to download the compTeamInfo.txt file from URL {val}')
            downloadCompTeamInfo = val

if downloadCompTeamInfo:
    if re.search(os.getenv('zulipDomain'), downloadCompTeamInfo):
        # The file is on the chat server, get a temp zulip URL to download it
        uploadPath = str(re.search("\/user_uploads\/.*", downloadCompTeamInfo).group())
        if uploadPath:
            publicCompTeamInfoURL = zulip.getUploadFileURL(uploadPath)
            if debug:
                print(f'Got public Zulip URL: {publicCompTeamInfoURL}')
            
            # Download the file locally
            dl = requests.get("https://" + os.getenv('zulipDomain') + publicCompTeamInfoURL)

            try:
                with open(compTeamInfoTXT, "wb") as f:
                    f.write(dl.content)
            except:
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "**ERROR**: Unable to download the Zulip compTeamInfo.txt file.")
                exit(-1)
        else:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "**ERROR**: Unable to parse the Zulip user upload location to download the compTeamInfo.txt file.")
            exit(-1)
        
    else:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "**ERROR**: Currently only support downloading a file from the chat server.")
        exit(-1)


# Let's start closing out everything that was previously setup
zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "We're tearin' it down!")

# Load the compTeamInfo from the warm-up
if os.path.isfile(compTeamInfoTXT):
    with open(compTeamInfoTXT, 'r') as file:
        compTeamInfo = json.load(file)
else:
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "**ERROR**: The compTeamInfo file doesn't exist! Was looing for " + compTeamInfoTXT)
    print(compTeamInfoTXT + " file missing")
    exit(-1)

if debug:
    print(compTeamInfo)

# We'll go team by team to delete/disable users, clear chat history, remove groups (if needed), delete shared folders, etc
for team in compTeamInfo:
    if debug:
        print(f'Found team {team}')
    
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Cleaning up team {team}')

    # Look for users
    if 'users' in compTeamInfo[team]:
        if debug:
            print(f'Looping through users for team {team}')
        for username, userdata in compTeamInfo[team]['users'].items():
            # Look for authentik user info
            if 'authentik' in userdata:
                # Delete the authentik user based on pk
                response = requests.request("DELETE", "https://" + authentikDomain + "/api/v3/core/users/" + str(userdata['authentik']['pk']) + "/", headers=authentikHeaders)

                if debug:
                    print(response.status_code, response.text)
                
                if response.status_code != 204:
                    # Error deleting user
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t delete authentik user {username} with pk of {str(userdata["authentik"]["pk"])}')
            
            # Delete Mantis user
            if 'mantis' in userdata:
                try:
                    mantis.deleteUser(userdata['mantis']['id'])
                except Exception as ex:
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to delete Mantis user {username}.\r\nException:\r\n```\r\n{ex}\r\n```')
            
            # Delete the Nextcloud user
            try:
                nextcloud.deleteUser(username)
            except Exception as ex:
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Issue deleting Nextcloud user {username}.\r\nException:\r\n```\r\n{ex}\r\n```')

            # Look for Zulip user info
            if 'zulip' in userdata:
                # Disable the zulip user account
                try:
                    zulip.deactivateUserID(userdata['zulip']['id'])
                except Exception as ex:
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t deactivate Zulip user {username} with id of {str(userdata["zulip"]["id"])}.\r\nException:\r\n```\r\n{ex}\r\n```')
    
    # Look for Nextcloud group folders
    if 'folders' in compTeamInfo[team]:
        if debug:
            print(f'Looping through Nextcloud folders for team {team}')
        
        for folderName, folderID in compTeamInfo[team]['folders'].items():
            if debug:
                print(f'Trying to delete Nextcloud group folder "{folderName}" with ID of {folderID}')
            
            try:
                nextcloud.deleteGroupFolder(folderID)
            except Exception as ex:
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t delete Nextcloud folder "{folderName}" with id of {folderID}.\r\nException:\r\n```\r\n{ex}\r\n```')
    
    # Look for team groups
    if 'groups' in compTeamInfo[team]:
        # Look for Nextcloud groups
        if 'Nextcloud' in compTeamInfo[team]['groups']:
            if debug:
                print('Looping through Nextcloud groups')
            for group in compTeamInfo[team]['groups']['Nextcloud']:
                try:
                    nextcloud.deleteGroup(group)
                except Exception as ex:
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t delete Nextcloud group "{group}".\r\nException:\r\n```\r\n{ex}\r\n```')
    
    # Clear out Zulip team channel messages
    if 'channels' in compTeamInfo[team]:
        if debug:
            print(f'Looping through team {team} Zulip channels to flush messages')
        
        for channelName, channelID in compTeamInfo[team]['channels'].items():
            if debug:
                print(f'Trying to get all topics from {channelName} with ID of {channelID}')
            
            try:
                topics = zulip.getChannelTopics(channelID)
                if topics:
                    for topic in topics:
                        zulip.deleteChannelTopic(channelID, topic)
            except Exception as ex:
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t clear out Zulip channel messages for channel "{channelName}".\r\nException:\r\n```\r\n{ex}\r\n```')
    
    # Delete Mantis projects
    if 'support' in compTeamInfo[team]:
        if 'MantisProjID' in compTeamInfo[team]['support']:
            try:
                mantis.deleteProject(compTeamInfo[team]['support']['MantisProjID'])
            except Exception as ex:
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to delete Mantis project with ID {compTeamInfo[team]["support"]["MantisProjID"]}.\r\nException:\r\n```{ex}\r\n```')



# We're all done
zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "We tore it down!")

# Do some cleanup
try:
    os.remove(compTeamInfoTXT)
    
    # Look for team upload link TXT files
    files = os.listdir()
    for file in files:
        if re.match("Team-\d+-Upload-Link.txt", file):
            os.remove(file)
    
    # Delete the teampasswords.csv
    if os.path.isfile(teamPassCSV):
        os.remove(teamPassCSV)
except Exception as ex:
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Couldn\'t delete certain files from the system during cleanup. May need to manually remove them.\r\nException:\r\n```\r\n{ex}\r\n```')