from google_auth_oauthlib.flow import InstalledAppFlow
import json

def generate_token(client_secrets_file ="./assets/token/client_secrets.json", token_file="token.json"):
    """
    Run the OAuth 2.0 flow to authenticate and generate a persistent token file.

    Args:
        client_secrets_file (str): Path to the client secrets JSON file.
        token_file (str): Path to save the generated token file.
    """
    # Define the required scopes for YouTube
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
    credentials = flow.run_local_server(port=0)

    # Save the credentials to a JSON file
    with open(token_file, "w") as token:
        token.write(credentials.to_json())
        print(f"Token saved to {token_file}")
