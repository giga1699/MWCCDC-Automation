import random
import string
import requests
import re
import os

# This function is used to process a CSV line to pull out team username, team number, and user password; returns a dict with username, teamNum, and password
# Modify this as needed for your specific event
def getTeamUserPass(line, teamNameRegex):
    username = line[0]
    password = line[1]

    # Check username format
    if not re.match(teamNameRegex, username):
        raise Exception("Username not in correct format")

    group = str(line[0])[:-1]
    groupnum = group[-2:]

    return {"username": username, "teamNum": groupnum, "password": password}

# Modify this function if you want to build in your own way of generating a short link from a given URL. Return the short link
def generateShortLink(fullURL, debug=False):
    # Generate random short code
    short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=5))

    if debug:
        print(short_code)

    # Create the short link for the upload URL
    headers = {
        "Authorization": "Bearer " + os.getenv('snappToken')
    }
    payload = {
        "data": {
        "shortcode": short_code,
        "originalUrl": fullURL,
        "user": {
            "connect": {
            "username": os.getenv('snappUser')
            }
        },
        "tag": {
            "connect": {
            "slug": "upload-link"
            }
        }
        }
    }

    response = requests.request("POST", "https://" + os.getenv('snappDomain') + "/api/snapp/create", headers=headers, json=payload)

    if debug:
        print(response.text)
    
    if response.status_code != 201:
        raise Exception('Error creating short link!', response.status_code, response.text)
    
    return "https://" + os.getenv('snappDomain') + "/" + short_code
