import requests
from time import sleep

class CCDCZulip:
    def checkError(self, zulipResponse):
        if zulipResponse.json()['result'] != "success":
            raise Exception(f'Unknown error when trying to send a Zulip request. Response:\r\n{zulipResponse.text}\r\n{zulipResponse.json()}')

    def zulipBackoff(self, zulipResponse):
        # Check response to see if we need to backoff API calls for a while
        if zulipResponse.json()['result'] == "error" and 'code' in zulipResponse.json() and zulipResponse.json()['code'] == "RATE_LIMIT_HIT":
            # We've sent too many API calls. Let's wait for 5 seconds past the retry-after point. This should be recoverable
            hold = int(zulipResponse.json()['retry-after']) + 5
            if self.debug:
                print(f'Hit a rate limit. Backing off for {hold} seconds...')
            sleep(hold)
            return True
        
        # No need to backoff, we can safely continue
        return False

    def sendChannelMessage(self, zulipChannel, zulipTopic, zulipMessage):
        # While loop for certain error handling to repeat message attempt
        while True:
            # Send zulip message to a given channel under a given topic
            zulipPayload = {
            "type": "stream",
            "to": zulipChannel,
            "topic": zulipTopic,
            "content": zulipMessage,
            }
            if self.debug:
                print(f'Sending channel message as defined in payload: {zulipPayload}')

            response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/messages", data=zulipPayload)

            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

    def findUserIDByEmail(self, searchEmail):
        while True:
            # Find uer by email
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users/" + searchEmail)
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break

        if response.json()['result'] == "success" and "user" in response.json():
            return response.json()['user']['user_id']
            
        elif response.json()['result'] == "error" and response.json()['msg'] == "No such user":
            return False
        else:
            raise Exception(f'Unknown error when trying to findUserIDByEmail. Response:\n{response.text}')

    def activateUserID(self, userID):
        while True:
            response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users/" + userID + "/reactivate")
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

    def deactivateUserID(self, userID):
        while True:
            response = requests.request("DELETE", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users/" + str(userID))
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

    def createUser(self, email, password, name):
        while True:
            zulipPayload = {
                "email": email,
                "password": password,
                "full_name": name,
            }
            response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users", data=zulipPayload)

            if not self.zulipBackoff(response):
                break

        # Check for some other kind of error
        self.checkError(response)

    def getAllChannels(self):
        while True:
            zulipPayload = {
                "include_all": "true",
            }
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/streams", data=zulipPayload)
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

        # Return the JSON output
        return response.json()
    
    def getChannelTopics(self, channelID):
        while True:
            # Find all topics in each channel
            zulipPayload = {
                "allow_empty_topic_name": "true",
            }
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users/me/" + str(channelID) + "/topics", data=zulipPayload)

            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        self.checkError(response)

        # Iterate through the topics, and build an array of names
        topicNames = []
        for topic in response.json()['topics']:
            topicNames.append(topic['name'])
        
        if self.debug:
            print(topicNames)
        
        if topicNames:
            return topicNames
        
        return False
    
    def getUserIDByEmail(self, email):
        while True:
            response = requests.request("GET", f'https://{self.zulipEmail}:{self.zulipToken}@{self.zulipDomain}/api/v1/users/{email}')

            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        if response.json()['result'] == "success":
            return response.json()['user']["user_id"]
        else:
            return False
    
    def deleteChannelTopic(self, channelID, channelTopic):
        while True:
            # Find all topics in each channel
            zulipPayload = {
                "topic_name": channelTopic,
            }
            response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/streams/" + str(channelID) + "/delete_topic", data=zulipPayload)

            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        self.checkError(response)

    def getAllGroups(self):
        while True:
            zulipPayload = {
                "include_deactivated_groups": "true",
            }
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/user_groups", data=zulipPayload)
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

        # Return the JSON output
        return response.json()

    def getAllUsers(self):
        # Get all users
        while True:
            zulipPayload = {
                "include_custom_profile_fields": "true",
            }
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users", data=zulipPayload)
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

        # Return the JSON output
        return response.json()

    def uploadFile(self, filename):
        while True:
            try:
                with open(filename, 'rb') as f:
                    response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/user_uploads", files={filename: f})
            except:
                return False
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

        # Return the JSON output
        return response.json()

    def isUserInGroup(self, userID, groupID):
        # Check if the user is a member of the specified group
        while True:
            zulipPayload = {
                "direct_member_only": "true",
            }
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/user_groups/" + str(groupID) + "/members/" + str(userID), data=zulipPayload)
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

        if response.json()['is_user_group_member'] == "true":
            return True
        
        return False
    
    def addUserToGroup(self, userID, groupID):
        # Add a user to the specified group
        while True:
            zulipPayload = {
                "add": "[" + str(userID) + "]",
            }
            response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/user_groups/" + str(groupID) + "/members", data=zulipPayload)
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)
    
    def isUserInChannel(self, userID, channelID):
        # Check if the user is subscribed to the specified channel
        while True:
            response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/streams/" + str(channelID) + "/members")
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

        for sub in response.json()['subscribers']:
            if int(sub) == int(userID):
                if self.debug:
                    print(f'Zulip user ID {userID} is a member of channel ID {channelID}')
                return True
        
        if self.debug:
            print(f'Zulip user ID {userID} is NOT a member of channel ID {channelID}')
        return False
    
    def subscribeUserToChannel(self, userID, channelName):
        # Subscribe the specified user ID to the given channel name
        while True:
            zulipPayload = {
                'subscriptions': "[{\"name\": \"" + channelName + "\"}]",
                'principals': f'[{userID}]',
            }
            response = requests.request("POST", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users/me/subscriptions", data=zulipPayload)
            
            if self.debug:
                print(response.text)
            
            if not self.zulipBackoff(response):
                break
        
        # Check for some other kind of error
        self.checkError(response)

    def __init__(self, zulipEmail, zulipToken, zulipDomain="chat.ccdc.events", debug=False):
        self.zulipEmail = zulipEmail
        self.zulipToken = zulipToken
        self.zulipDomain = zulipDomain
        self.debug = debug

        # Try to open up a connection to test API creds
        response = requests.request("GET", "https://" + self.zulipEmail + ":" + self.zulipToken + "@" + self.zulipDomain + "/api/v1/users/me")
        if self.debug:
            print(response.text)

        if 'result' in response.json() and response.json()['result'] == "success":
            # We made a good connection
            if self.debug:
                print("Good connection!")
        else:
            raise Exception("Unable to connect to Zulip using supplied credentials and configuration!")