import requests
from xml.dom import minidom
import re


class CCDCNextcloud:
    def deleteUser(self, username):
        headers = {
            'OCS-APIRequest': 'true'
        }
        if self.debug:
            print(f'Deleting Nextcloud user {username}')
        
        response = requests.request("DELETE", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/ocs/v1.php/cloud/users/" + username, headers=headers)
        if self.debug:
            print(response.status_code, response.text)
        
        if not re.search("<statuscode>100</statuscode>", response.text):
            raise Exception(f'Unable to delete Nextcloud user "{username}"', response.status_code, response.text)
    
    def createGroup(self, groupName):
        #Create the group in Nextcloud
        if self.debug:
            print(f'Creating nextcloud group "{groupName}"')
        headers = {
            'OCS-APIRequest': 'true'
        }
        payload = {
            'groupid': groupName
        }
        response = requests.request("POST", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/ocs/v1.php/cloud/groups", headers=headers, data=payload)

        if self.debug:
            print(response.text)
        
        if not re.search("<status>ok</status>", response.text):
            # If status wasn't okay, make sure it's only because the group already existed (statuscode 102)
            if not re.search("<statuscode>102</statuscode>", response.text):
                raise Exception(f'Unable to create Nextcloud group "{groupName}"', response.text)
    
    def deleteGroup(self, groupName):
        # Delete a group in Nextcloud
        if self.debug:
            print(f'Deleting Nextcloud group {groupName}')
        
        headers = {
            'OCS-APIRequest': 'true'
        }
        response = requests.request("DELETE", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/ocs/v1.php/cloud/groups/" + str(groupName), headers=headers)

        if self.debug:
            print(response.status_code, response.text)
        
        if not re.search("<status>ok</status>", response.text):
            # If status wasn't okay, make sure it's only because the group doesn't exist (statuscode 101)
            if not re.search("<statuscode>101</statuscode>", response.text):
                raise Exception(f'Unable to delete Nextcloud group "{groupName}"', response.text)
    
    def createGroupFolder(self, folderName):
        #Create the group folder in Nextcloud
        if self.debug:
            print(f'Creating nextcloud group folder "{folderName}"')
        headers = {
            'OCS-APIRequest': 'true'
        }
        payload = {
            'mountpoint': folderName,
            'bucket': 'null'
        }
        response = requests.request("POST", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/index.php/apps/groupfolders/folders", headers=headers, data=payload)

        if response.status_code != 200:
            raise Exception(f'Unable to create Nextcloud group folder "{folderName}"', response.text)

        if self.debug:
            print(response.text)
        
        parser = minidom.parseString(response.text)
        folderid = parser.getElementsByTagName('id')[0].firstChild.data
        if self.debug:
            print("Folder ID: " + folderid)
        
        return folderid
    
    def deleteGroupFolder(self, folderID):
        if self.debug:
            print(f'Trying to delete Nextcloud group folder with ID {folderID}')

        headers = {
            'OCS-APIRequest': 'true'
        }
        response = requests.request("DELETE", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/index.php/apps/groupfolders/folders/" + str(folderID), headers=headers)

        if self.debug:
            print(response.status_code, response.text)
        
        if response.status_code != 200:
            raise Exception(f'Unable to delete Nextcloud group folder with ID {folderID}', response.status_code, response.text)
    
    def addGroupToFolder(self, folderID, groupName):
        #Create the group folder in Nextcloud
        if self.debug:
            print(f'Adding group "{groupName}" to shared folder ID {folderID}')
        headers = {
            'OCS-APIRequest': 'true'
        }
        payload = {
            'group': groupName,
        }
        response = requests.request("POST", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/index.php/apps/groupfolders/folders/" + folderID + "/groups", headers=headers, data=payload)

        if response.status_code != 200:
            raise Exception(f'Unable to add group "{groupName}" to Nextcloud folder ID {folderID}', response.text)

        if self.debug:
            print(response.text)
    
    def setFolderGroupPerms(self, folderID, groupName, permissions):
        # Set the permissions for a given group assigned to the specified folder
        # I honestly haven't figured out what the integer value correlates to, but here's what I do know
        ## 23 is write and share; no delete
        ## 15 is write and delete; no share
        ## 1 is read only?
        
        if self.debug:
            print(f'Adding permission int {permissions} for group {groupName} on folder ID {folderID}')

        headers = {
            'OCS-APIRequest': 'true'
        }
        payload = {
            'permissions': permissions,
        }
        response = requests.request("POST", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/index.php/apps/groupfolders/folders/" + folderID + "/groups/" + groupName, headers=headers, data=payload)

        if self.debug:
            print(response.text)
        
        if response.status_code != 200:
            raise Exception(f'Unable to set permissions for "{groupName}" on folder ID {folderID} with setting {permissions}', response.text)
    
    def createUploadOnlyShare(self, folderPath):
        if self.debug:
            print(f'Creating upload only share for folder "{folderPath}"')

        headers = {
            'OCS-APIRequest': 'true'
        }
        payload = {
            "path": folderPath,
            "shareType": "3",
            "permissions": "4",
        }
        response = requests.request("POST", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/ocs/v2.php/apps/files_sharing/api/v1/shares", headers=headers, data=payload)

        if self.debug:
            print(response.text)
        
        if response.status_code != 200:
            raise Exception(f'Unable to create upload only folder share for "{folderPath}"', response.text)

        urlRegex = "(?<=\<url\>)(.+)(?=\</url\>)"
        urlSearch = re.search(urlRegex, response.text)
        shareURL = urlSearch.group()
        if not shareURL:
            raise Exception(f'Unable to create upload only folder share for "{folderPath}". Couldn\'t find URL.', response.text)

        if self.debug:
            print(shareURL)

        return shareURL

    def __init__(self, nextcloudUser, nextcloudToken, nextcloudDomain="docs.ccdc.events", debug=False):
        self.nextcloudUser = nextcloudUser
        self.nextcloudToken = nextcloudToken
        self.nextcloudDomain = nextcloudDomain
        self.debug = debug

        # Test connecting to the Nextcloud API
        nextcloudHeader = {
            "OCS-APIRequest": "true",
        }
        response = requests.request("GET", "https://" + self.nextcloudUser + ":" + self.nextcloudToken + "@" + self.nextcloudDomain + "/ocs/v1.php/cloud/users/" + self.nextcloudUser, headers=nextcloudHeader)

        if self.debug:
            print(response.text)
        
        if re.search("<status>ok</status>", response.text):
            if self.debug:
                print("Good Nextcloud connection!")
        else:
            raise Exception("Unable to connect to Nextcloud.", response.text)