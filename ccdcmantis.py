import requests
import json

class CCDCMantis:
    def createUser(self, username):
        if self.debug:
            print(f'Creating Mantis user {username}')
        
        mantisHeader = {
            "Authorization": self.mantisToken,
            'Content-Type': 'application/json'
        }
        mantisPayload = json.dumps({
            "username": username
        })
        response = requests.request("POST", "https://" + self.mantisDomain + "/api/rest/users/", headers=mantisHeader, data=mantisPayload)

        if self.debug:
            print(response.status_code, response.text)
        
        if response.status_code != 201:
            raise Exception(f'Unable to create Mantis user {username}', response.status_code, response.text)
        
        return response.json()['user']['id']
    
    def deleteUser(self, userID):
        if self.debug:
            print(f'Deleting Mantis user with id {userID}')
        
        mantisHeader = {
            "Authorization": self.mantisToken,
        }
        response = requests.request("DELETE", "https://" + self.mantisDomain + "/api/rest/users/" + str(userID), headers=mantisHeader)

        if self.debug:
            print(response.status_code, response.text)
        
        if response.status_code != 204:
            raise Exception(f'Unable to delete Mantis user with ID {userID}', response.status_code, response.text)
    
    def createProject(self, projectName, parentProjectID=False):
        if self.debug:
            print(f'Creating Mantis project {projectName}')
        
        mantisHeader = {
            "Authorization": self.mantisToken,
            'Content-Type': 'application/json'
        }
        mantisPayload = json.dumps({
            "name": projectName,
            "status": {
                "name": "development"
            },
            "view_state": {
                "id": 50,
                "name": "private",
                "label": "private"
            },
            "inherit_global": False
        })
        response = requests.request("POST", "https://" + self.mantisDomain + "/api/rest/projects/", headers=mantisHeader, data=mantisPayload)

        if self.debug:
            print(response.status_code, response.text)
        
        if response.status_code != 201:
            raise Exception(f'Unable to create Mantis project {projectName}', response.status_code, response.text)
        
        projectID = response.json()['project']['id']

        if parentProjectID:
            if self.debug:
                print(f'Adding project {projectName} as sub-project of ID {parentProjectID}')
            mantisPayload = json.dumps({
                "project": {
                    "name": projectName,
                },
                "inherit_parent": True
            })
            response = requests.request("POST", "https://" + self.mantisDomain + "/api/rest/projects/" + str(parentProjectID) + "/subprojects", headers=mantisHeader, data=mantisPayload)

            if self.debug:
                print(response.status_code, response.text)
            
            if response.status_code != 204:
                raise Exception(f'Unable to make Mantis project {projectID} a sub-project of parent ID {parentProjectID}', response.status_code, response.text)

        return projectID
    
    def deleteProject(self, projectID):
        if self.debug:
            print(f'Deleting Mantis project with id {projectID}')
        
        mantisHeader = {
            "Authorization": self.mantisToken,
            'Content-Type': 'application/json'
        }
        response = requests.request("DELETE", "https://" + self.mantisDomain + "/api/rest/projects/" + str(projectID), headers=mantisHeader)

        if self.debug:
            print(response.status_code, response.text)
        
        if response.status_code != 204:
            raise Exception(f'Unable to delete Mantis project with ID {projectID}', response.status_code, response.text)
    
    def addUserToProject(self, username, projectID, accessLevel="reporter"):
        if self.debug:
            print(f'Adding Mantis user {username} to project with id {projectID}')
        
        mantisHeader = {
            "Authorization": self.mantisToken,
            'Content-Type': 'application/json'
        }
        mantisPayload = json.dumps({
            "user": {
                "name": username
            },
            "access_level": {
                "name": accessLevel
            }
        })
        response = requests.request("PUT", "https://" + self.mantisDomain + "/api/rest/projects/" + str(projectID) + "/users/", headers=mantisHeader, data=mantisPayload)

        if self.debug:
            print(response.status_code, response.text)
        
        if response.status_code != 204:
            raise Exception(f'Unable to add Mantis user {username} to project with ID {projectID}', response.status_code, response.text)

    def __init__(self, mantisToken, mantisDomain="support.ccdc.events", debug=False):
        self.mantisToken = mantisToken
        self.mantisDomain = mantisDomain
        self.debug = debug

        # Test connecting to the Mantis
        mantisHeader = {
            "Authorization": self.mantisToken,
        }
        response = requests.request("GET", "https://" + self.mantisDomain + "/api/rest/users/me?select=id", headers=mantisHeader)

        if self.debug:
            print(response.text)
        
        if response.status_code == 200:
            if self.debug:
                print("Good Mantis connection!")
        else:
            raise Exception("Unable to connect to Mantis.", response.status_code, response.text)