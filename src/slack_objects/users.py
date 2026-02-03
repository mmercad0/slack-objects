"""
Created by:     Marcos E. Mercado
Description:    Users class definition to take actions related to Slack users.
"""
#from libraries_and_globals import *
#from myClasses.PC_Bot_SlackAPIcaller import Slack_API_caller as API_caller
#from myClasses.Slack.IDP_groups import IDP_groups
import json
#from slack_bolt import App

class Users:
    def __init__(self, global_vars: global_variables, client: App.client, logger: logging.Logger, user_id: str="") -> None:
        """ Constructor gets the information for the user. """

        self.global_vars = global_vars  # Global variables class instanciated in app.py with test or production values.
        self.user_id = user_id
        self.client = client
        self.logger = logger
        
        self.invite_user_wait_time = Tier_2

        if user_id: # If a user_id was provided when instantiating the class:
            try:
                # Call the users.info method using the WebClient    https://api.slack.com/methods/users.info/code
                result = client.users_info(user = self.user_id)

                #logger.debug(result)
                #print(f"\t** Result of users_info invoked in {__name__} constructor is: {result}")

                if result['ok']:
                    self.attributes = result['user']
                else:
                    raise SlackApiError(f"Error when calling users_info in {__name__} constructor.", result)

            except SlackApiError as e:
                logger.error(f"Error fetching '{self.user_id}' user info: {e}")


    def is_contingent_worker(self) -> bool:
        """ Method that determines whether a user is a contingent_worker (CW).
        The first approach to this method is to use the name of the user and look for prefix '[External]'
        """
        cw_label = '[External]'  # label that identifies a CW

        if cw_label in self.attributes['real_name'] or cw_label in self.attributes['profile']['display_name']: # What we see as 'Full name' and 'Display name' fields, respectively.
            return True
        else:
            return False


    def is_guest(self) -> bool:
        """ Method that determines whether a user is a single or multi-channel guest in Slack. """
        if self.attributes['is_restricted'] or self.attributes['is_ultra_restricted']:
            return True
        else:
            return False


    def make_multi_channel_guest(self, token: str, scim_version: str = 'v1') -> requests.Response:
        """Method that changes the user's role in Slack to a multi-channel guest.
        It receives a User OAuth Token and a SCIM version (defaults to 'v1', which is production as of June 2023)"""

        if scim_version == 'v2':    # from https://api.slack.com/admins/scim2#patch-users-id
            api_type = 'scim v2'

            payload = {
                "schemas": [
                    "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                ],
                "Operations": [
                    {
                        "path": "urn:ietf:params:scim:schemas:extension:slack:guest:2.0:User",
                        "op": "add",
                        "value": {
                            "type": "multi"
                        }
                    }
                ]
            }
        elif scim_version == 'v1':  # Payload below from Tina. Also very similar payload described in: https://api.slack.com/admins/scim#patch-users-id:~:text=To%20convert%20a%20full%20member%20to%20a%20multi%2Dchannel%20guest%20without%20an%20expiration%20date%2C%20use%3A
            api_type = 'scim v1'

            payload = {
                "schemas": ["urn:scim:schemas:core:1.0",
                    "urn:scim:schemas:extension:enterprise:1.0",
                    "urn:scim:schemas:extension:slack:guest:1.0"],

                "urn:scim:schemas:extension:slack:guest:1.0": {
                    "type": "multi"
                }
        }
        else:
            raise NotImplementedError(f"Invalid SCIM version: {api_caller.scim_version}")

        try:
            api_caller = API_caller(token, api_type)
            response = api_caller.callAPI(f"Users/{self.user_id}", "PATCH", str(payload))   # Note that we have to convert the payload into a string
        except Exception as e:
            (api_caller_exception_response, api_caller_exception_response_text) = e.args
            response = api_caller_exception_response

        return response


    def remove_from_channels(self, token: str, client: WebClient, logger: logging.Logger, channel_ids: list) -> None:
        """Method that receives a list of channel ids and the user is removed from those channels."""
        wait_time = Tier_3     # Rate limit for conversations.kick is Tier 3 (50+ calls per minute = 1.2 seconds between each call)
        api_caller = API_caller(token)

        for channel_id in channel_ids:
            try:
                #result = client.conversations_kick(channel=channel_id, user=self.user_id)   # Removed because this didn't work for removing the test user. Kept getting 'not_in_channel' error. https://api.slack.com/methods/conversations.kick
                payload = {
                    'channel_ids' : channel_id,
                    'user_id' : self.user_id
                    }

                response = api_caller.callAPI("admin.conversations.remove", "POST", payload)  # This is a 'hidden' method provided by Tina
                logger.debug(response.text)
                print(f"\t** Result of admin.conversations.remove invoked in {__name__} remove_from_channels method is: {response.text}")

                data = json.loads(response.text)

                if data['ok']:
                    print(f"Successfully removed user '{self.user_id}' from channel '{channel_id}'.")
                    time.sleep(wait_time)
                else:
                    raise SlackApiError(f"Error when removing from channels in {__name__}", data)

            except SlackApiError as e:
                logger.error(f"Error removing user '{self.user_id}' from channel '{channel_id}': {e}")


    def remove_from_workspaces(self, client: WebClient, logger: logging.Logger, workspace_ids: list, keep: list = []) -> None:
        """Method that receives a list of workspace ids and the user is removed from those workspaces.
        If a list of workspace ids to keep is provided, they won't be removed from the user."""
        wait_time = Tier_2     # Rate limit for admin.users.remove is Tier 2 (20+ calls per minute = 3 seconds between each call)
        
        token = self.global_vars.user_token     # We use the user token (instead of the bot token) because of the admin API that we'll call.

        for workspace_id in workspace_ids:
            if workspace_id not in keep:
                try:
                    result = client.admin_users_remove(token=token, team_id=workspace_id, user_id=self.user_id)  # https://api.slack.com/methods/admin.users.remove
                    logger.debug(result)
                    logging_message = f"\t** Removing user from workspaces: Result of admin_users_remove invoked in {__name__} remove_from_workspaces method for user '<@{self.user_id}>' and workspace '{workspace_id}' is: {result}"
                    print(logging_message)
                    client.chat_postMessage(text=logging_message, channel=self.global_vars.admin_logs_channel_id)

                    if result['ok']:
                        print(f"Successfully removed user '{self.user_id}' from workspace '{workspace_id}'.")
                        time.sleep(wait_time)
                    else:
                        raise SlackApiError(f"Error when removing from workspaces in {__name__}", result)

                except SlackApiError as e:
                    logging_message = f"Error removing user '<@{self.user_id}>' from workspace '{workspace_id}': {e}"
                    print(logging_message)
                    logger.error(logging_message)
                    client.chat_postMessage(text=logging_message, channel=self.global_vars.admin_logs_channel_id)

    def ap_studio_process(self) -> None:
        """Method that first checks if the user is CW and if it is:
        1. Converts user to MCG
        2. Removes user from org-wide default channels
        3. Removes user from all other workspaces
        """
        print(f"Starting AP Studio process for user: '{self.user_id}' - '{self.attributes['real_name']}''")

        if self.is_contingent_worker():
            print("** User is a CW.")
            text = "CW - "
            
            # Convert user to multi-channel guest.
            response_MCG = self.make_multi_channel_guest(token=self.global_vars.user_token, scim_version='v1')    #  We need to use the User OAuth Token for SCIM API calls (defined globally).

            if response_MCG.ok:
                print("\t> Converted to MCG.")
                text += "Successfully converted user to MCG. "            
            else:
                text += f"Error converting to MCG: {response_MCG} "
                
            # Remove user from org-wide default channels.
            print("\t> Removing from org-wide channels...")
            self.remove_from_channels(self.global_vars.user_token, self.client, self.logger, self.global_vars.org_wide_default_channels)

            # Remove user from other workspaces.
            print("\t> Removing from other workspaces...")
            current_workspaces = self.attributes['enterprise_user']['teams']
            self.remove_from_workspaces(self.client, self.logger, current_workspaces, keep=[self.global_vars.External_AP_workspace]) # Remove all current workspaces, only keep EXTERNAL - Activision Publishing

            print("\t Done.")
        else:
            print("** User is an FTE. No changes occured.")
            text = "FTE - "

        text += f"User: '<@{self.user_id}>' - '{self.attributes['real_name']}' (username '{self.attributes['name']}' | displayname '{self.attributes['profile']['display_name']}'). User was added to the #general channel of EXTERNAL - Activision Publishing (T053M58JVC2) workspace."
        self.client.chat_postMessage(text = text, channel=self.global_vars.External_AP_logging_channel)


    def get_userId_from_email(self, email: str) -> str:
        """Method that receives an email address and, if successful, returns the Slack user ID corresponding to that email.
        If there is an error obtaining the user id, the method returns an empty string."""
        wait_time = Tier_3
        user_id =""

        try:
            response = self.client.users_lookupByEmail(email=email)   # https://api.slack.com/methods/users.lookupByEmail
            self.logger.info(response)

            if response.data['ok']:
                user_id = response.data['user']['id']
            else:
                raise SlackApiError(f"Error when looking up a user with email '{email}' in {__name__}", response)

        except SlackApiError as e:
             self.logger.error(f"Error in {__name__} - get_userId_from_email method using email '{email}': {e}")
        finally:
            time.sleep(wait_time)
            return user_id


    def is_user_authorized(self, service_name: str, auth_level: str = "read") -> bool:
        """Method that receives a service name and determines whether the instantiated user is authorized to modify the service.
            As of August 2023, this is determined by whether the user_id is in the IdP group corresponding to the service.
            Feb 2025, added auth level to differentiate when there's read-only or beyond. This was for info requests vs. data modification request.
                another update in Feb 2025 was to change the IdP groups to a list instead of a single string. It's a list because of atvi and bl AD groups."""

        authorized = False

        if auth_level == "write":
            group_ids = self.global_vars.auth_IdP_groups_write_access[service_name]
        else:
            group_ids = self.global_vars.auth_IdP_groups_read_access[service_name]

        idp_groups = IDP_groups(self.global_vars)    # instantiate class IDP_groups to use is_member() method

        for group_id in group_ids:
            if idp_groups.is_member(self.user_id, group_id):  # If user is in the group, will return True. Otherwise, will return False.
                authorized = True
                break

        return authorized
 
    
    def invite_user(self, channel_ids: str, email: str, team_id: str, email_password_policy_enabled: bool = False) -> str:
        """Method that sends an invite for a user to join a workspace and returns the API response as string.
        channel_ids is a comma-separated list of channel ids for the user to join."""
        wait_time = self.invite_user_wait_time

        api_caller = API_caller(self.global_vars.user_token)    # Since it's an admin API, need to use the user token instead of the bot token

        payload = {
            'channel_ids' : channel_ids,    # comma-separated list of channel ids as string
            'email' : email,
            'team_id': team_id,
            'email_password_policy_enabled': email_password_policy_enabled  # Parameter that determines if we allow the user to sign in via email and password.
            }

        try:
            response = api_caller.callAPI("admin.users.invite", "POST", payload)    # https://api.slack.com/methods/admin.users.invite
            time.sleep(wait_time)           
            data = json.loads(response.text)
            
            self.logger.debug(data)
            print(f"** Result of admin.users.invite invoked in {__name__} invite_user method is: {data}\n")

            if data['ok']:
                print(f"Successfully sent invite to '{email}' in {__name__}")
            else:
                print(f"Error when inviting user with email {email} in {__name__}: {data}\n")
            
            result = response.text

        except SlackApiError as e:
            self.logger.error(f"Error when inviting user '{email}' in {__name__}: {e}")
            result = f"SlackApiError: {e}"
            
        return result.replace(',','|')  # Replacing commas for the csv file