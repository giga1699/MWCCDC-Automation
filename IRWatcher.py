import os
from dotenv import load_dotenv
import requests
import re
import json
from time import sleep

# Load .env file if it exists
if os.path.isfile(".env"):
    load_dotenv()

username = os.getenv("NISEUser")
password = os.getenv("NISEPass")

loginTokenRegex = "(?<=<input type=\"hidden\" name=\"csrfmiddlewaretoken\" value=\").*(?=\">)"
irUploadRegex = "<a href=\"\/files\/inject\/8\/submission\/[0-9]+\/.*\" class=\"table_link\">\n.*\n.*\n.*\n.*<\/a>"
irUploadURLRegex = "\/files\/inject\/8\/submission\/[0-9]+\/.*(?=\" class=\"table_link\">)"
invalidRegex = "<s>.*<\/s>"

niseURL = os.getenv("NISEURL")
irPage = niseURL + "/injects/" + str(os.getenv("IRWatcherInjectNum")) + "/"

webhookURL = os.getenv("IRWatcherWebhook")

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
unknownIRs = False
lastTotalIRs = 0

# Monitor loop
while True:

    irResults = niseSession.get(irPage)

    if irResults.status_code != 200:
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

        if uploadURL not in knownIRs and not invalidInject:
            unknownIRs = True

            knownIRs.append(uploadURL)
            message = f'Team {teamNum} submitted {fileName}\nLink: {niseURL}{uploadURL}'
            # print(message)

            webhookHeaders = {
                "Content-Type": "application/json",
            }
            webhookData = {
                "text": message,
            }
            # print(webhookData)

            sendWebhook = requests.request("POST", webhookURL, headers=webhookHeaders, data=json.dumps(webhookData))
            if sendWebhook.status_code != 200:
                print(f'Status code: {sendWebhook.status_code}\nText: {sendWebhook.text}')
        elif uploadURL in knownIRs and invalidInject:
            knownIRs.remove(uploadURL)
    
    totalIRs = len(knownIRs)

    if unknownIRs or totalIRs != lastTotalIRs:
        webhookHeaders = {
            "Content-Type": "application/json",
        }
        webhookData = {
            "text": f'Total uploads marked valid: {totalIRs}',
        }
        # print(webhookData)

        sendWebhook = requests.request("POST", webhookURL, headers=webhookHeaders, data=json.dumps(webhookData))
        if sendWebhook.status_code != 200:
            print(f'Status code: {sendWebhook.status_code}\nText: {sendWebhook.text}')
    
    print(f'Total uploads this check: {totalIRs}')

    unknownIRs = False
    lastTotalIRs = totalIRs

    sleep(60)