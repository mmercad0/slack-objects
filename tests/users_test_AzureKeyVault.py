from PC_Azure import Azure_Key_Vault as Key_Vault
from slack_objects import SlackObjectsConfig, SlackObjectsClient

slack_key_vault = Key_Vault("Your-Azure-KeyVault-Name")    #Your Azure Key Vault name
secret_name = "Your-Secret-Name"

cfg = SlackObjectsConfig(
    user_token=slack_key_vault.get_secret(secret_name)
)

slack = SlackObjectsClient(cfg)

users = slack.users()

email = input("Enter the email address to look up the user ID: ")

user_id = users.get_user_id_from_email(email)

print(f"The user ID for email '{email}' is: {user_id}")