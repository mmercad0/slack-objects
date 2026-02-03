#from config import SlackObjectsConfig
#from client import SlackObjectsClient
from slack_objects import SlackObjectsConfig, SlackObjectsClient

cfg = SlackObjectsConfig(
    bot_token ="xoxb-your-bot-token",
    user_token="xoxp-your-user-token",
    scim_token="your-scim-token",
)

slack = SlackObjectsClient(cfg)

users = slack.users()
user_id = users.get_userId_from_email("jane.doe@example.com")
