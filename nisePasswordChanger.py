import os
from dotenv import load_dotenv
import requests
import re
import json
from time import sleep
import ccdczulip
import operator
from bs4 import BeautifulSoup
import csv
import ccdchelpers
import sys

debug=False

# Load .env file if it exists
if os.path.isfile(".env"):
    load_dotenv()

username = os.getenv("NISEUser")
password = os.getenv("NISEPass")

csrfTokenRegex = "(?<=<input type=\"hidden\" name=\"csrfmiddlewaretoken\" value=\").*(?=\">)"

zulipOperationsChannel="operations"
zulipOperationsTopic="automation-messages"
zulipOperationsGroup="Black Team"

if os.getenv('zulipOperationsChannel'):
    zulipOperationsChannel=os.getenv('zulipOperationsChannel')
if os.getenv('zulipOperationsTopic'):
    zulipOperationsChannel=os.getenv('zulipOperationsTopic')
if os.getenv('zulipOperationsGroup'):
    zulipOperationsGroup=os.getenv('zulipOperationsGroup')

niseURL = os.getenv("NISEURL")

nisePassCSV = "NISE.csv"

# Create the Zulip connection
zulip = ccdczulip.CCDCZulip(os.getenv('zulipEmail'), os.getenv('zulipToken'), debug=debug)
zulipAdmin = ccdczulip.CCDCZulip(os.getenv('zulipAdminEmail'), os.getenv('zulipAdminToken'), debug=debug)

# Pull it from Vantage
# curl -s -H "X-API-Key: <admin-key>" https://vantage.ccdc.events/api/ext-accounts/NISE
for arg in sys.argv[1:]:
    if "=" in arg:
        key, val = arg.split("=", 1)
        if key == "vantageExtAccount":
            vantageExtAccount = val
        elif key == "vantageApiKey":
            vantageApiKey = val
        elif key == "niseURL":
            niseURL = val
try:
    if vantageApiKey and vantageExtAccount:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Attempting to download the {vantageExtAccount} external accounts from Vantage')
        vantageHeaders = {
            'X-API-Key': vantageApiKey
        }
        vantageCSV = requests.get(f'https://vantage.ccdc.events/api/ext-accounts/{vantageExtAccount}', headers=vantageHeaders)
        if vantageCSV.status_code != 200:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Error downloading from Vantage!\n```\n{vantageCSV}\n```\nExiting...')
            exit(-1)
        
        csvFile = open(nisePassCSV, "w")
        csvFile.write(vantageCSV.text)
        csvFile.close()

except Exception as e:
    if debug:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Exception downloading from Vantage!\n```\n{e}\n```\nExiting...')
        exit(-1)

# Load user/pass CSV
usersPage = niseURL + "/users/"
NISEUsers = {}
# Check that the CSV file exists
if not os.path.isfile(nisePassCSV):
    zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'@*{zulipOperationsGroup}* **ERROR**: The NISE password CSV file specified doesn\'t exist. Please fix the defined CSV file, and restart the script!')
    exit(-1)
# Open up the CSV and start processing the team buildout
with open(nisePassCSV, newline='') as file:
  nisePass = csv.reader(file)
  for lines in nisePass:
    niseUser = lines[0]
    nisePass = lines[1]
    if username not in NISEUsers:
        NISEUsers.update({niseUser: nisePass})
    else:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, "Found a duplicate username in NISE password CSV, ignoring duplicate!")

niseSession = requests.Session()

# Get login page
loginPage = niseSession.get(niseURL + "/users/login/")
if loginPage.status_code != 200:
    raise Exception("Unable to reach NISE login page")

# Find loginToken
loginToken = re.search(csrfTokenRegex, loginPage.text)
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

zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f"NISE password changer logged into NISE at {niseURL}, getting user accounts.")


usersPage = niseSession.get(usersPage)

userParser = BeautifulSoup(usersPage.text, 'html.parser')

teamUsers = {}

for element in userParser.find_all('a', string=re.compile("team[0-9]+[a-i]")):
    href = element['href']
    username = re.search("team[0-9]+[a-i]", element.get_text()).group()


    if username not in teamUsers:
        teamUsers.update({f'{username}': href})

#print(teamUsers)

zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Found the following NISE users:\n```\n{list(teamUsers.keys())}\n```')

for user,userhref in teamUsers.items():

    userConfigPage = niseURL + userhref

    userPage = niseSession.get(userConfigPage)

    configParser = BeautifulSoup(userPage.text, 'html.parser')

    # We need csrf token, username, password, is_active, groups, teams
    inputs = configParser.find_all('input', {"name": ["csrfmiddlewaretoken", "username", "password", "is_active", "groups"]})
    team = configParser.find('select', {"name": "teams"}).find('option', {'selected': ''})

    formdata = {}

    if team:
        formdata.update({'teams': team.get('value')})

    for formInput in inputs:
        inputType = formInput.get('type')
        inputValue = formInput.get('value')
        inputName = formInput.get('name')

        if inputType == "text" or inputType == "hidden":
            formdata.update({inputName: inputValue})
        
        if inputType == "checkbox":
            if formInput.get('value') and (formInput.get('checked') or formInput.get('checked') == ""):
                if inputName not in formdata:
                    formdata.update({inputName: inputValue})
                else:
                    if isinstance(formdata[inputName], list):
                        formdata[inputName].append(inputValue)
                    else:
                        currentVal = formdata[inputName]
                        formdata[inputName] = [currentVal, inputValue]
            elif formInput.get('checked') or formInput.get('checked') == "":
                formdata.update({formInput.get('name'): "on"})
    
    if formdata['username'] in NISEUsers and formdata['password'] != NISEUsers[formdata['username']]:

        formdata['password'] = NISEUsers[formdata['username']]

        # Enable user if they're disabled
        if formdata['is_active'] != "on":
            formdata['is_active'] = "on"

        pwChange = niseSession.post(userConfigPage, data=formdata, headers={'Content-Type': 'application/x-www-form-urlencoded', 'Referer': userConfigPage})

        if pwChange.status_code == 200:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Changed password for {formdata["username"]}')
        else:
            zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Unable to change password for {formdata["username"]}.\nStatus code: {pwChange.status_code}')
    
    elif formdata['username'] in NISEUsers:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'NISE password for {formdata["username"]} already matches CSV.')
    else:
        zulip.sendChannelMessage(zulipOperationsChannel, zulipOperationsTopic, f'Couldn\'t find updated password for {formdata["username"]} from NISE CSV provided, skipping this user.')
    
os.unlink(nisePassCSV)