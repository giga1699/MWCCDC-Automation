import os
from dotenv import load_dotenv
import requests
import re
import json
from time import sleep
import ccdczulip

debug=False

# Load .env file if it exists
if os.path.isfile(".env"):
    load_dotenv()

username = os.getenv("NISEUser")
password = os.getenv("NISEPass")

loginTokenRegex = "(?<=<input type=\"hidden\" name=\"csrfmiddlewaretoken\" value=\").*(?=\">)"
irUploadRegex = "<a href=\"\/files\/inject\/" + str(os.getenv("IRWatcherInjectNum")) + "\/submission\/[0-9]+\/.*\" class=\"table_link\">\n.*\n.*\n.*\n.*<\/a>"
irUploadURLRegex = "\/files\/inject\/" + str(os.getenv("IRWatcherInjectNum")) + "\/submission\/[0-9]+\/.*(?=\" class=\"table_link\">)"
invalidRegex = "<s>.*<\/s>"

zulipRedTeamChannel="red-team"
zulipRedTopic="IR Reports"

niseURL = os.getenv("NISEURL")
irPage = niseURL + "/injects/" + str(os.getenv("IRWatcherInjectNum")) + "/"

# Create the Zulip connection
zulip = ccdczulip.CCDCZulip(os.getenv('zulipIREmail'), os.getenv('zulipIRToken'), debug=debug)
zulipAdmin = ccdczulip.CCDCZulip(os.getenv('zulipAdminEmail'), os.getenv('zulipAdminToken'), debug=debug)

zulip.sendChannelMessage(zulipRedTeamChannel, zulipRedTopic, "Starting IR watcher...")

niseSession = requests.Session()

# Get login page
loginPage = niseSession.get(niseURL + "/users/login/")
if loginPage.status_code != 200:
    raise Exception("Unable to reach NISE login page")

# Find loginToken
loginToken = re.search(loginTokenRegex, loginPage.text)
# print(loginToken.group())

# Post to login page
loginPayload = {
    "username": username,
    "password": password,
    "csrfmiddlewaretoken": loginToken.group(),
}
loginHeaders = {
    "Referer": niseURL + "/users/login/"
}
loginSubmit = niseSession.request("POST", niseURL + "/users/login/", headers=loginHeaders, data=loginPayload)
if loginSubmit.status_code != 200:
    raise Exception(f'Unable to submit login!\nStatus Code: {loginSubmit.status_code}\nResponse text: {loginSubmit.text}')

# print(loginSubmit.cookies.get_dict())

knownIRs = []
invalidIRs = []
unknownIRs = False
lastTotalIRs = 0

zulip.sendChannelMessage(zulipRedTeamChannel, zulipRedTopic, "IR watcher logged into NISE, and begining monitor loop.")

# Monitor loop
while True:

    irResults = niseSession.get(irPage)

    if irResults.status_code != 200:
        zulip.sendChannelMessage(zulipRedTeamChannel, zulipRedTopic, "Error getting IR results page. Exiting!")
        raise Exception(f'Error getting IR results page.\nStatus code: {irResults.status_code}\nText: {irResults.text}')
        exit(-1)

    irUploads = re.findall(irUploadRegex, irResults.text)
    # print(irUploads)

    for upload in irUploads:
        invalidInject = False
        # print(upload)

        if re.search(invalidRegex, upload):
            invalidInject = True
            # print("Found invalid inject")

        uploadURL = re.search(irUploadURLRegex, upload).group()

        uploadSplit = uploadURL.split('/')
        teamNum = int(uploadSplit[5]) - 1
        fileName = uploadSplit[6]

        if uploadURL not in knownIRs and uploadURL not in invalidIRs and not invalidInject:
            unknownIRs = True

            knownIRs.append(uploadURL)
            message = f'Team {teamNum} submitted {fileName}\nLink: {niseURL}{uploadURL}'
            # print(message)

            zulip.sendChannelMessage(f'Team {teamNum:02} IR', fileName, f'@*Red Team* @*Team {teamNum:02}* A new IR report has been submitted\nLink: {niseURL}{uploadURL}')

            if os.getenv('copyIRtoZulip') == "True":
                try:
                    # Try to download file
                    fileDL = niseSession.get(f'{niseURL}{uploadURL}')

                    with open(fileName, 'wb') as f:
                        f.write(fileDL.content)
                    
                    if os.path.isfile(fileName):
                        # Try to upload file
                        response = zulip.uploadFile(fileName)
                        if response:
                            zulip.sendChannelMessage(f'Team {teamNum:02} IR', fileName, f'Copy of IR report: [{response["filename"]}]({response["url"]})')

                        # Delete the file
                        os.remove(fileName)
                except Exception as ex:
                    zulip.sendChannelMessage(zulipRedTeamChannel, zulipRedTopic, f'Failed to download/upload {fileName} for team {teamNum:02}')
                    print(ex)

        elif uploadURL in knownIRs and invalidInject:
            knownIRs.remove(uploadURL)
            invalidIRs.append(uploadURL)

            zulip.sendChannelMessage(f'Team {teamNum:02} IR', fileName, f'This upload was marked as INVALID.')
        
        elif uploadURL in invalidIRs and not invalidInject:
            invalidIRs.remove(uploadURL)
            knownIRs.append(uploadURL)

            zulip.sendChannelMessage(f'Team {teamNum:02} IR', fileName, f'This upload was marked as VALID.')
    
    totalIRs = len(knownIRs)

    if unknownIRs or totalIRs != lastTotalIRs:
        # Calculate IRs by team
        teamCount = {}
        for link in knownIRs:
            teamCountNum = str(int(link.split('/')[5]) - 1)

            if teamCountNum not in teamCount:
                teamCount.update({teamCountNum: 1})
            else:
                teamCount.update({teamCountNum: teamCount[teamCountNum] + 1})
        
        if debug:
            print(teamCount)
        
        # Send team breakdown to red-team channel
        teamBreakdown = '| Team | IRs |\n| :---: | :---: |\n'
        for team, count in teamCount.items():
            teamBreakdown += f'| {int(team):02} | {count} |\n'
        
        if debug:
            print(teamBreakdown)
        
        zulip.sendChannelMessage(zulipRedTeamChannel, zulipRedTopic, teamBreakdown)

        # Send total valid IRs to red-team channel
        zulip.sendChannelMessage(zulipRedTeamChannel, zulipRedTopic, f'Total uploads marked valid: {totalIRs}')
    
    print(f'Total uploads this check: {totalIRs}')

    unknownIRs = False
    lastTotalIRs = totalIRs

    sleep(60)
