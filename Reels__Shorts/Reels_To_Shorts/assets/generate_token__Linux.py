from google_auth_oauthlib.flow import Flow
import json

def generate_token(client_secrets_file, token_file="token.json"):
    """
    Perform manual OAuth 2.0 flow for headless environments without launching a browser.

    Args:
        client_secrets_file (str): Path to the client secrets JSON file.
        token_file (str): Path to save the generated token file.
    """
    # Define the required scopes for YouTube
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    # Initialize the OAuth flow
    flow = Flow.from_client_secrets_file(client_secrets_file, scopes=scopes)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"  # Set redirect URI for manual authentication

    # Generate the authorization URL
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    # Provide the URL for manual authentication
    print(f"Please go to the following URL to authorize this application:\n{auth_url}")

    # Ask the user to paste the authorization code
    auth_code = input("Enter the authorization code: ")

    # Exchange the authorization code for credentials
    flow.fetch_token(code=auth_code)

    # Save the credentials to a file
    credentials = flow.credentials
    with open(token_file, "w") as token:
        token.write(credentials.to_json())
    print(f"Token saved to {token_file}")
