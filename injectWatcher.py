import os
from dotenv import load_dotenv
import requests
import re
import json
from time import sleep
import ccdczulip
from bs4 import BeautifulSoup

# NISE Inject States
## pending (not viewable by teams yet)
## active (viewable and accepting submissions)
## expired (past due date)
## rejecting (no longer accepting submissions)

debug=False

# Load .env file if it exists
if os.path.isfile(".env"):
    load_dotenv()

username = os.getenv("NISEUser")
password = os.getenv("NISEPass")

loginTokenRegex = "(?<=<input type=\"hidden\" name=\"csrfmiddlewaretoken\" value=\").*(?=\">)"

niseURL = os.getenv("NISEURL")
injectsPage = niseURL + "/injects/"

# Create the Zulip connection
zulip = ccdczulip.CCDCZulip(os.getenv('zulipInjectEmail'), os.getenv('zulipInjectToken'), debug=debug)
zulipAdmin = ccdczulip.CCDCZulip(os.getenv('zulipAdminEmail'), os.getenv('zulipAdminToken'), debug=debug)

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

injects = {}

# Main loop
while True:

    print('Checking...')

    injectResults = niseSession.get(injectsPage)

    injectParser = BeautifulSoup(injectResults.text, 'html.parser')

    injectTable = injectParser.find_all("table", class_="wide_table")[1]

    if debug:
        print(injectTable)

    injectsList = injectTable.find_all("tr")
    injectsList.pop(0)
    #print(injectsList)

    for inject in injectsList:
        injectName = inject.select("td:nth-of-type(2) > a")[0].get_text().replace("\n", "").lstrip().rstrip()
        injectLink = inject.get("href")
        injectNum = re.search('(?<=\/injects\/)\d+(?=\/)', injectLink).group()
        injectStatus = inject.get("class")[0]
        injectStart = inject.select("td:nth-of-type(5)")[0].get_text()
        injectDue = inject.select("td:nth-of-type(6)")[0].get_text()
        injectReject = inject.select("td:nth-of-type(7)")[0].get_text()

        if injectNum not in injects:
            injects.update({injectNum: 
                {
                    "name": injectName,
                    "link": injectLink,
                    "status": injectStatus,
                    "start": injectStart,
                    "due": injectDue,
                    "reject": injectReject,
                }
            })
        elif injectNum in injects and injects[injectNum]["status"] != injectStatus:
            zulip.sendChannelMessage("white-team", "Inject Monitor", f'Inject "{injectName}" (NISE #{injectNum}) changed status from {injects[injectNum]["status"]} to {injectStatus}')

            if not ((injects[injectNum]["status"] == "pending" and injectStatus == "active") or (injects[injectNum]["status"] == "active" and injectStatus == "expired") or (injects[injectNum]["status"] == "active" and injectStatus == "rejecting") or (injects[injectNum]["status"] == "expired" and injectStatus == "rejecting")):
                zulip.sendChannelMessage("white-team", "Inject Monitor", f'@*White Team* This may be an invalid inject state transition!')
            
            if injects[injectNum]["status"] == "pending" and injectStatus == "active":
                zulip.sendChannelMessage('Competition Announcements', 'Inject Alerts', f'@**everyone** An inject has just gone active!\nInject name: {injectName}\nInject due: {injectDue}\nInject reject: {injectReject}')

            injects[injectNum]["status"] = injectStatus

        if debug:
            print(f'Inject Number: {injectNum}\nInject Name: {injectName}\nInject State: {injectStatus}\nInject Link: {injectLink}\nInject Start: {injectStart}\nInject Due: {injectDue}\nInject Reject: {injectReject}\n')

    if debug:
        print(json.dumps(injects, indent=2))

    sleep(10)