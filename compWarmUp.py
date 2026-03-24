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
mantisMasterProjectID="1"
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
zulipRedChannelRegex="Team \d+ IR"

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
#### Mantis
##### id
### Zulip Channels
#### Channel name: ID
### Folders (nextcloud)
#### Folder name: folderID
### Groups
#### Zulip {name: id}
#### Nextcloud [list]
### Support
#### Projects
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
if os.getenv('mantisMasterProjectID'):
    teamPassCSV=os.getenv('mantisMasterProjectID')
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
if os.getenv('zulipRedChannelRegex'):
    zulipGreenChannelRegex=os.getenv('zulipRedChannelRegex')

downloadTeamPass = False
for arg in sys.argv[1:]:
    if "=" in arg:
        key, val = arg.split("=", 1)
        if key == "downloadTeamPass":
            if debug:
                print(f'Going to download the teampasswords.csv file from URL {val}')
            downloadTeamPass = val

# Download the team password CSV if downloadTeamPass is present, or if the environment variable exists
if downloadTeamPass or os.getenv('teamPassDownloadURL'):
    url = downloadTeamPass if downloadTeamPass else os.getenv('teamPassDownloadURL')
    if debug:
        print(f'Downloading team password CSV from "{url}"')
    
    # Check for a Nextcloud link
    if re.search(os.getenv('ncDomain'), url):
        # Download the file from Nextcloud
        # Need to transform the link first
        shareID = url.split('/')[-1]
        url = f'https://{os.getenv("ncDomain")}/public.php/dav/files/{shareID}'
    
    r = requests.get(url)

    try:
        with open(teamPassCSV, 'wb') as f:
            f.write(r.content)
    except:
        print(f'Unable to download the team password CSV! Exiting...')
        exit(-1)
    
    exit(0)

# Output default values if debugging enabled
if debug:
    print(f'Default values set for this run...\n\nTeam Name Regex: {teamNameRegex}\r\nzulipOperationsChannel: {zulipOperationsChannel}\r\nzulipOperationsTopic: {zulipOperationsTopic}')

# Create the Zulip connection
zulip = ccdczulip.CCDCZulip(os.getenv('zulipEmail'), os.getenv('zulipToken'), debug=debug)
try:
    zulipAdmin = ccdczulip.CCDCZulip(os.getenv('zulipAdminEmail'), os.getenv('zulipAdminToken'), debug=debug)
except:
    print("Couldn't create zulipAdmin connection")

# Create the Nextcloud connection
nextcloud = ccdcnextcloud.CCDCNextcloud(os.getenv('ncAppUser'), os.getenv('ncAppPass'), os.getenv('ncDomain'), debug=debug)

# Create the Mantis connection
mantis = ccdcmantis.CCDCMantis(os.getenv('mantisToken'), os.getenv('mantisDomain'), debug=debug)

# Let's kick this off!
zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "Beginning competition warm-up script...")


# Get Zulip info
zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "Getting base information from Zulip...")

# Get all of the zulip channels
zulipChannels = {}
for channel in zulip.getAllChannels()['streams']:
    if debug:
        print(f'Channel "{channel["name"]}" has ID {channel["stream_id"]}')
    
    zulipChannels.update({channel['name']: channel['stream_id']})

if debug:
    print(zulipChannels)

# Try to get the groups, but it probably won't work
zulipGroups = {}
try:
    for group in zulipAdmin.getAllGroups()['user_groups']:
        if debug:
            print(f'Group "{group["name"]}" had ID of {group["id"]}')

        zulipGroups.update({group['name']: group['id']})
except Exception as err:
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to get all groups. This is likely because you\'re running this tool as a bot, and they don\'t have access to get all groups.\r\nError message:\r\n```\r\n{err}\r\n```\r\nFailing over to manual group provisioning...')
    # Define the important zulip groups; since bots can't get the group listing... this is painful
    zulipGroups = defaultZulipGroups

if debug:
    print(zulipGroups)

# Get all the zulip users; focus is on team accounts, if they exist; This requires the zulip "full_name" to be defined per the team username regex, and no other accounts should have that name format. If it's something else, this code will need to be modified to work properly.
zulipTeamUsers = {}
for user in zulip.getAllUsers()['members']:
    if debug:
        print(f'User "{user["full_name"]}" has delivery e-mail "{user["delivery_email"]}", generic e-mail "{user["email"]} and ID {user["user_id"]}')

    if re.match(teamNameRegex, user['full_name']):
        if user['delivery_email'] and user['delivery_email'] == user['full_name'] + teamUserDomainName:
            zulipTeamUsers.update({user['full_name']: {"email": user['delivery_email'], "id": user['user_id']}})
        elif user['delivery_email']:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Zulip user {user["full_name"]} looks like a team account, but doesn\'t have the right e-mail address.\r\nE-Mail: {user["delivery_email"]}\r\nUserID: {user["user_id"]}.\r\nYou may need to manually modify this user, but account will be added as if it\'s an actual team account. Please ask an admin to update the user\'s e-mail address if necessary.')
            zulipTeamUsers.update({user['full_name']: {"email": user['delivery_email'], "id": user['user_id']}})
        else:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Zulip user {user["full_name"]} looks like a team account, but has a hidden delivery e-mail.\r\nGeneric E-Mail: {user["email"]}\r\nUserID: {user["user_id"]}\r\nYou may need to manually modify this user, but account will be added as if it\'s an actual team account.\r\nPlease change e-mail visibiilty back to administrators for this account if this script needs to see the account.')
            zulipTeamUsers.update({user['full_name']: {"email": user['email'], "id": user['user_id']}})

if debug:
    print(zulipTeamUsers)


# Check that the CSV file exists
if not os.path.isfile(teamPassCSV):
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: The team password CSV file specified doesn\'t exist. Please fix the defined CSV file, and restart the script!')
    exit(-1)

# Open up the CSV and start processing the team buildout
with open(teamPassCSV, newline='') as file:
  teamPass = csv.reader(file)
  for lines in teamPass:
    try:
        userInfo = ccdchelpers.getTeamUserPass(lines, teamNameRegex)

        if debug:
            print(userInfo)
    except Exception as ex:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Could not properly parse the user/pass CSV as defined in getTeamUserPass. Please review the code and try again.')
        print(ex)
        exit(-1)
    
    # Check if we already know about this team
    if userInfo['teamNum'] not in compTeamInfo:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Starting on Team {userInfo["teamNum"]}')
        # We have a new team, let's setup the info for that team
        compTeamInfo.update({userInfo['teamNum']: {
            "users": {},
            "channels": {},
            "folders": {},
            "groups": {},
            "support": {},
            "urls": {}
        }})

        # Let's iterate through the channels, look for the team number, and add those channels to the dict as well
        for name, id in zulipChannels.items():
            if re.match(zulipBlueChannelRegex, name) or re.match(zulipOrangeChannelRegex, name) or re.match(zulipGreenChannelRegex, name) or re.match(zulipRedChannelRegex, name):
                # We found a channel that seems to match the regex; Let's look for the team number in the channel name now
                if re.search(userInfo['teamNum'], name):
                    # We found what is likely a team channel; add it to the compTeamInfo
                    compTeamInfo[f'{userInfo["teamNum"]}']['channels'].update({name: id})
        
        # Let's interate through the groups, look for the team group, and add that group to the dict
        for group, groupID in zulipGroups.items():
            if re.match(zulipBlueGroupRegex, group):
                if re.search(userInfo['teamNum'], group):
                    if 'zulip' not in compTeamInfo[f'{userInfo["teamNum"]}']['groups']:
                        compTeamInfo[f'{userInfo["teamNum"]}']['groups'].update({'zulip': {}})
                    compTeamInfo[f'{userInfo["teamNum"]}']['groups']['zulip'].update({group: groupID})
        
        # Create a Mantis project for the team
        try:
            if mantisMasterProjectID:
                teamMantisProjectID = mantis.createProject("Team " + userInfo['teamNum'], mantisMasterProjectID)
            else:
                teamMantisProjectID = mantis.createProject("Team " + userInfo['teamNum'])
            compTeamInfo[userInfo['teamNum']]['support'].update({"MantisProjID": teamMantisProjectID})
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to create the Mantis project "Team {userInfo["teamNum"]}".\r\nException:\r\n```\r\n{ex}\r\n```')
        
        # Make sure there's a Nextcloud Group created, and add that information to compTeamInfo
        try:
            nextcloud.createGroup("Team-Blue-" + userInfo['teamNum'])
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to create the Nextcloud group "Team-Blue-{userInfo["teamNum"]}"!')
            print(ex)
            exit(-1)
        if "Nextcloud" not in compTeamInfo[f'{userInfo["teamNum"]}']['groups']:
            compTeamInfo[f'{userInfo["teamNum"]}']['groups'].update({"Nextcloud": []})
        compTeamInfo[f'{userInfo["teamNum"]}']['groups']["Nextcloud"].append(f'Team-Blue-{userInfo["teamNum"]}')
        try:
            nextcloud.createGroup("Team-Blue-" + userInfo['teamNum'] + "-Coach")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to create the Nextcloud group "Team-Blue-{userInfo["teamNum"]}-Coach"!')
            print(ex)
            exit(-1)
        compTeamInfo[f'{userInfo["teamNum"]}']['groups']["Nextcloud"].append(f'Team-Blue-{userInfo["teamNum"]}-Coach')

        # Create the Nextcloud Group Folder
        try:
            folderID = nextcloud.createGroupFolder("Team-" + userInfo['teamNum'])
            compTeamInfo[f'{userInfo["teamNum"]}']['folders'].update({f'Team-{userInfo["teamNum"]}': folderID})
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to create the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
            exit(-1)
        # Add groups to Group Folder
        try:
            nextcloud.addGroupToFolder(folderID, "Team-Blue-" + userInfo['teamNum'])
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to add blue team group to the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
            exit(-1)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-Blue-" + userInfo['teamNum'], '15')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to set blue team group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
            exit(-1)

        try:
            nextcloud.addGroupToFolder(folderID, "Team-Blue-" + userInfo['teamNum'] + "-Coach")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to add blue team coach group to the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-Blue-" + userInfo['teamNum'] + "-Coach", '1')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to set blue team coach group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)

        try:
            nextcloud.addGroupToFolder(folderID, "Team-White")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to add white team group to the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-White", '1')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to set white team coach group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)

        try:
            nextcloud.addGroupToFolder(folderID, "Team-Black")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to add black team group to the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-Black", '1')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to set black team coach group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}"!')
            print(ex)
        
        # Create the Nextcloud Group Upload Folder
        try:
            folderID = nextcloud.createGroupFolder("Team-" + userInfo['teamNum'] + "/Uploads")
            compTeamInfo[f'{userInfo["teamNum"]}']['folders'].update({f'Team-{userInfo["teamNum"]}/Uploads': folderID})
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to create the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
            exit(-1)
        # Add groups to Group Folder
        try:
            nextcloud.addGroupToFolder(folderID, "Team-Blue-" + userInfo['teamNum'])
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to add blue team group to the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
            exit(-1)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-Blue-" + userInfo['teamNum'], '15')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to set blue team group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
            exit(-1)

        try:
            nextcloud.addGroupToFolder(folderID, "Team-Blue-" + userInfo['teamNum'] + "-Coach")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to add blue team coach group to the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-Blue-" + userInfo['teamNum'] + "-Coach", '1')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to set blue team coach group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)

        try:
            nextcloud.addGroupToFolder(folderID, "Team-White")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to add white team group to the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-White", '1')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to set white team coach group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)

        try:
            nextcloud.addGroupToFolder(folderID, "Team-Black")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to add black team group to the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
        try:
            nextcloud.setFolderGroupPerms(folderID, "Team-Black", '23')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to set black team coach group permissions on the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
        
        # Create a link to the team's upload only share
        try:
            uploadLink = nextcloud.createUploadOnlyShare("Team-" + userInfo['teamNum'] + "/Uploads")
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to create an upload share link for the Nextcloud folder "Team-{userInfo["teamNum"]}/Uploads"!')
            print(ex)
        compTeamInfo[userInfo['teamNum']]['urls'].update({"Nextcloud-Upload-Share": uploadLink})

        try:
            # Create a short link to give to students for uploads quickly
            shortURL = ccdchelpers.generateShortLink(uploadLink, debug)

            # Add short link to compTeamInfo
            compTeamInfo[userInfo['teamNum']]['urls'].update({"Nextcloud-Upload-Share-Short": shortURL})

            # Send short code to ops for awareness
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Created short upload link for Team {userInfo["teamNum"]}: {shortURL}\nFull link: {uploadLink}')

            # Figure out blue team channel, and notify them of the short URL
            blueTeamNotifyUploadLink = False
            for channel in compTeamInfo[userInfo['teamNum']]['channels']:
                if re.match(zulipBlueChannelRegex, channel):
                    try:
                        linkID = uploadLink.split('/')[-1]
                        zulip.sendChannelMessage(channel, zulipBlueAnnounceTopic, f'Created short upload link for Team {userInfo["teamNum"]}: {shortURL}\nFull link: {uploadLink}')
                        zulip.sendChannelMessage(channel, zulipBlueAnnounceTopic, f'To upload with curl, try the following command...\n```\ncurl -T <filename> -u "{linkID}:" -H "X-Requested-With: XMLHttpRequest" https://{os.getenv("ncDomain")}/public.php/dav/files/{linkID}/<filename>\n```')
                        blueTeamNotifyUploadLink = True
                    except Exception as ex:
                        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN** Unable to send Team {userInfo["teamNum"]} a message in channel {channel}, topic {zulipBlueAnnounceTopic}, about their short link.\nException:\n```\n{ex}\n```')
                        if debug:
                            print(ex)
            if not blueTeamNotifyUploadLink:
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN** Unable to send Team {userInfo["teamNum"]} a message in channel {channel}, topic {zulipBlueAnnounceTopic}, about their short link. Couldn\'t find their channel?')
            
            # Write short link out to text file
            # with open("Team-" + userInfo['teamNum'] + "-Upload-Link.txt", 'w') as f:
            #     f.write(f'Team {userInfo["teamNum"]} Upload Link: {shortURL}')

        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error creating short upload link for Team {userInfo["teamNum"]}.\r\nException:\r\n```\r\n{ex}\r\n```')

        ######We're done with the new team stuff. Whew!###########


    # Add the user to the compTeamInfo
    compTeamInfo[f'{userInfo["teamNum"]}']['users'].update({userInfo['username']: {}})

    # Create an authentik user
    payload = json.dumps({
      "username": userInfo['username'],
      "name": userInfo['username'],
      "email": userInfo['username'] + teamUserDomainName,
      "is_active": True,
      "groups": [
        os.getenv('authentikMasterBlueGroup')
      ],
      "path": "blue-users",
      "type": "internal"
    })
    headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Authorization': 'Bearer ' + os.getenv('authentikToken')
    }

    response = requests.request("POST", "https://" + os.getenv('authDomain') + "/api/v3/core/users/", headers=headers, data=payload)

    if debug:
        print(response.text)
    
    if response.status_code != 201:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to create authentik user {userInfo["username"]}!\r\nResponse:\r\n```\r\n{response.text}\r\n```')
        print(response.text)
        exit(-1)

    compTeamInfo[f'{userInfo["teamNum"]}']['users'][userInfo['username']].update({"authentik": {"pk": response.json().get("pk")}})

    # Set authentik user password
    payload = json.dumps({
      "password": userInfo["password"]
    })
    headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + os.getenv('authentikToken')
    }

    userurl = "https://" + os.getenv('authDomain') + "/api/v3/core/users/" + str(compTeamInfo[f'{userInfo["teamNum"]}']['users'][userInfo['username']]['authentik']['pk']) + "/set_password/"
    response = requests.request("POST", userurl, headers=headers, data=payload)

    if debug:
        print(response)
    
    if response.status_code != 204:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: Unable to set authentik user {userInfo["username"]} password!\r\nResponse:\r\n```\r\n{response.text}\r\n```')
        print(response.text)
        exit(-1)
    
    # Create the Mantis user, and add them to the team project
    try:
        mantisUserID = mantis.createUser(userInfo['username'])
        mantis.addUserToProject(userInfo['username'], teamMantisProjectID)
        compTeamInfo[f'{userInfo["teamNum"]}']['users'][userInfo['username']].update({"mantis": {"id": mantisUserID}})
    except Exception as ex:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to create the Mantis user and/or add them to the team project.\r\nException:```\r\n{ex}\r\n```')


    # Check if we know about the Zulip user
    if userInfo['username'] in zulipTeamUsers:
        compTeamInfo[f'{userInfo["teamNum"]}']['users'][userInfo['username']].update({"zulip": zulipTeamUsers[userInfo['username']]})

        # Activate the user account
        try:
            zulip.activateUserID(str(zulipTeamUsers[userInfo['username']]['id']))
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to activate the Zulip user "{userInfo["username"]}", with ID of {str(zulipTeamUsers[userInfo["username"]["id"]])}.\r\nException:\r\n```\r\n{ex}\r\n```\r\nAsk an administrator to look into this before competition starts.')
    else:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Zulip user {userInfo["username"]} doesn\'t appear to exist. Will trying creating the user account. Ops may have to do some manual work with this account to get it in the right groups and channels.')
        try:
            zulip.createUser(userInfo['username'] + teamUserDomainName, userInfo['password'], userInfo['username'])
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**ERROR**: Unable to create the Zulip user "{userInfo["username"]}@{teamUserDomainName}"! Please fix the exception error that follows before running this tool again.\r\nException:\r\n```\r\n{ex}\r\n```')
            print(ex)
            exit(-1)

    # Check if the user is a member of the team's group. This apparently doesn't work for bots either :rip:
    if checkZulipGroupMembership:
        for group, groupID in compTeamInfo[userInfo['teamNum']]['groups']['zulip'].items():
            try:
                if not zulipAdmin.isUserInGroup(str(compTeamInfo[userInfo['teamNum']]['users'][userInfo['username']]['zulip']['id']), str(groupID)):
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Zulip user {userInfo["username"]} isn\'t in the Zulip group {group}! Attempting to assign them...')
                    zulipAdmin.addUserToGroup(str(compTeamInfo[userInfo['teamNum']]['users'][userInfo['username']]['zulip']['id']), str(groupID))
            except Exception as ex:
                if re.search("This endpoint does not accept bot requests", str(ex)):
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error checking/assigning group membership for Zulip user {userInfo["username"]}!\r\nBots can\'t use the specified endpoint.\r\nGiving up on checking group memberships!\r\nAdministrators/Ops will need to manually verify group memberships.')
                    checkZulipGroupMembership = False
                    break
                elif not re.search("User \d+ is already a member of this group", str(ex)):
                    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error checking/assigning group membership for Zulip user {userInfo["username"]}!\r\nException:\r\n```\r\n{ex}\r\n```')
    
    # Check if the user is subscribed to all the team channels
    for channel, channelID in compTeamInfo[userInfo['teamNum']]['channels'].items():
        try:
            if not zulip.isUserInChannel(compTeamInfo[userInfo['teamNum']]['users'][userInfo['username']]['zulip']['id'], channelID):
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Zulip user {userInfo["username"]} isn\'t in the Zulip channel {channel}! Attempting to assign them...')
                zulip.subscribeUserToChannel(compTeamInfo[userInfo['teamNum']]['users'][userInfo['username']]['zulip']['id'], channel)
                zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Success!')
        except Exception as ex:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Error checking/assigning channel subscription for Zulip user {userInfo["username"]} to channel {channel}!\r\nException:\r\n```\r\n{ex}\r\n```')


# We're all done, let's send the combined team info to ops to do any manual verification that needs to be completed
# First we need to write the compTeamInfo dict to a file
try:
    with open("compTeamInfo.txt", "w") as f:
        f.write(json.dumps(compTeamInfo, indent=2))
except:
    # Unable to write to the file
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to write the compTeamInfo.txt file to disk!')

# Send the wrap-up message
zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "@*" + zulipOperationsGroup + "* Competition warm-up script has completed. Final team information follows. Please look for warnings/errors above, and verify the below looks correct.")

# Try to upload the txt file to chat
if os.path.isfile("compTeamInfo.txt"):
    try:
        response = zulip.uploadFile("compTeamInfo.txt")
        if not response:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to upload the compTeamInfo.txt file!')
        else:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Resulting compTeamInfo: [{response["filename"]}]({response["url"]})')
            # Remove local copy of compTeamInfo.txt since we uploaded successfully to Zulip
            os.remove("compTeamInfo.txt")
    except Exception as ex:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'**WARN**: Unable to upload the compTeamInfo.txt file!\r\n```\r\n{ex}\r\n```')
        print(ex)

if debug:
    print(compTeamInfo)
    print(json.dumps(compTeamInfo, indent=2))

# if os.path.isfile('syncSupportUsers.py'):
#    os.system('python3 syncSupportUsers.py')