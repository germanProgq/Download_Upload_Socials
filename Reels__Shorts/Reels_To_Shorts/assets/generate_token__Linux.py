from google_auth_oauthlib.flow import InstalledAppFlow

def generate_token(client_secrets_file, token_file="token.json"):
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
    auth_url, _ = flow.authorization_url(prompt='consent')

    # Print the URL for manual authentication
    print(f"Please go to this URL and authorize access: {auth_url}")

    # Ask the user to input the authorization code
    auth_code = input("Enter the authorization code: ")
    credentials = flow.fetch_token(code=auth_code)

    # Save the credentials to a JSON file
    with open(token_file, "w") as token:
        token.write(credentials.to_json())
        print(f"Token saved to {token_file}")
