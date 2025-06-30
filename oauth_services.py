import base64
import sys
from flask import Flask, request, redirect, session, jsonify, Response
import requests
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import id_token
import os, json, pickle
from pathlib import Path
import threading
import asyncio
from werkzeug.middleware.proxy_fix import ProxyFix
import hashlib


# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('ENV_SECRET', 'your-secret-key-change-this-in-production')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

########################################################
# GOOGLE setup
CLIENT_SECRETS_GOOGLE = "credentials.json"
SCOPES_GOOGLE = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar",
]
REDIRECT_URI_GOOGLE = "https://testremotemcpserver.onrender.com/google/oauth2callback"

########################################################
# NOTION setup
CLIENT_ID_NOTION = None
CLIENT_SECRET_NOTION = None
REDIRECT_URI_NOTION = None
AUTH_URL_NOTION = None
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API_VERSION = "2022-06-28"

with open(os.path.join('credentials_notion.json')) as f:
    keys = json.load(f)
    CLIENT_ID_NOTION = keys.get('client_id')
    CLIENT_SECRET_NOTION = keys.get('client_secret') 
    REDIRECT_URI_NOTION = keys.get('redirect_uri')
    AUTH_URL_NOTION = keys.get('auth_url')

########################################################




SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
    
PICKLES_DIR = Path(SCRIPT_DIR) / 'Pickles'
PICKLES_DIR.mkdir(exist_ok=True)

def _save_creds(user_id: str, creds: Credentials, service: str):
    TOKEN_DIR = Path(PICKLES_DIR) / user_id
    TOKEN_DIR.mkdir(exist_ok=True)

    with open(TOKEN_DIR / f"{service}.pickle", "wb") as f:
        pickle.dump(creds, f)

def _load_creds(user_id: str, service: str) -> Credentials | None:
    TOKEN_DIR = Path(PICKLES_DIR) / user_id

    path = TOKEN_DIR / f"{service}.pickle"
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


@app.route("/authorize")
def authorize():
    """Redirect the user to Notion's consent screen."""
    client_code = request.args.get('client_code', 'default_client_code')
    session['client_code'] = client_code
    return redirect(AUTH_URL_NOTION)

@app.route("/auth/notion/callback")
def oauth_callback():
    """Handle Notion redirect → exchange `code` for `access_token`."""
    # Capture `code` param
    code = request.args.get("code")
    if not code:
        return f"Error: {request.args}", 400

    # Prepare Basic Auth header
    basic = base64.b64encode(f"{CLIENT_ID_NOTION}:{CLIENT_SECRET_NOTION}".encode()).decode()

    # Exchange code for token
    res = requests.post(
        NOTION_TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_API_VERSION,
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI_NOTION,
        },
        timeout=10,
    )
    if not res.ok:
        return f"Token exchange failed → {res.text}", 400

    _save_creds(session['client_code'], res.json(), "notion")  # Try to persist, but continue if it fails

    session.pop('client_code', None)

    return (
        f"<p>Authorization complete! You may close this tab now.</p>"
        f"<h3>User Data:</h3>"
        f"<pre>{json.dumps(res.json(), indent=2)}</pre>"
        # '<a href="/create_page">Create "Hello World" page ↗︎</a></p>'
    )



@app.route("/google/auth")
def start_google_auth():
    user_id = request.args.get('user_id', 'default_user')
    client_code = request.args.get('client_code', 'default_client_code')
    print("user_id", user_id)
    
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_GOOGLE,
            scopes=SCOPES_GOOGLE,
            redirect_uri=REDIRECT_URI_GOOGLE,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        print(state)
        print(auth_url)
        
        # Store flow data in session
        session['client_code'] = client_code
        session['oauth_state'] = state
        session['user_id'] = user_id
        session['flow_data'] = {
            'client_config': flow.client_config,
            'scopes': SCOPES_GOOGLE,
            'redirect_uri': REDIRECT_URI_GOOGLE
        }
        
        return redirect(auth_url)
    except Exception as e:
        return f"Error starting OAuth flow: {str(e)}", 500

@app.route("/google/oauth2callback")
def google_callback():
    try:
        # Verify state
        if 'oauth_state' not in session:
            return "Invalid session state", 400
        
        user_id = session.get('user_id', 'default_user')
        flow_data = session.get('flow_data')
        
        if not flow_data:
            return "Missing flow data", 400
        
        # Recreate flow
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_GOOGLE,
            scopes=SCOPES_GOOGLE,
            state=session["oauth_state"],
        )
        flow.redirect_uri = REDIRECT_URI_GOOGLE
        
        # Fetch token
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        
        # Save credentials
        creds = flow.credentials

        # gmail = build("gmail", "v1", credentials=creds)
        # unique_id = gmail.users().getProfile(userId="me").execute()["emailAddress"] 
        unique_id = session['client_code']

        _save_creds(unique_id, creds, "google")
        
        # Clear session
        session.pop('oauth_state', None)
        session.pop('user_id', None)
        session.pop('flow_data', None)
        
        return '''
        <html>
        <head><title>OAuth Success</title></head>
        <body>
            <h2>✅ Gmail connected successfully!</h2>
            <p>You can close this tab and return to your application.</p>
        </body>
        </html>
        '''
    except Exception as e:
        return f"Error in OAuth callback: {str(e)}", 500
    
@app.route('/creds-google')
def get_creds_google():
    """
    Get credentials from a pickle file with hash authentication
    Args:
        filename: Name of the pickle file (without .pickle extension)
    Query Parameters:
        hash: SHA256 hash of the secret value for authentication
    """
    try:
        # Get the hash parameter from query string
        provided_hash = request.args.get('hash')
        filename = request.args.get('filename')
        
        if not provided_hash:
            return jsonify({
                "status": "error",
                "message": "Hash parameter is required"
            }), 400
            
        if not filename:
            return jsonify({
                "status": "error",
                "message": "Filename parameter is required"
            }), 400
        
        # Get the secret from environment variables
        env_secret = os.environ.get('ENV_SECRET')
        if not env_secret:
            return jsonify({
                "status": "error",
                "message": "Server configuration error"
            }), 500
        
        # Compute hash of the environment secret
        expected_hash = hashlib.sha256(env_secret.encode()).hexdigest()
        
        # Compare hashes
        if provided_hash != expected_hash:
            return jsonify({
                "status": "error",
                "message": "Invalid hash"
            }), 403
        
        # If hashes match, proceed to get credentials
        creds = _load_creds(filename, "google")
        if creds:
            return jsonify({
                "status": "success",
                "credentials": {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"No credentials found for {filename}"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@app.route('/creds-notion')
def get_creds_notion():
    """
    Get Notion credentials from a pickle file with hash authentication
    Args:
        filename: Name of the pickle file (without .pickle extension)
    Query Parameters:
        hash: SHA256 hash of the secret value for authentication
    """
    try:
        # Get the hash parameter from query string
        provided_hash = request.args.get('hash')
        filename = request.args.get('filename')
        
        if not provided_hash:
            return jsonify({
                "status": "error",
                "message": "Hash parameter is required"
            }), 400
            
        if not filename:
            return jsonify({
                "status": "error",
                "message": "Filename parameter is required"
            }), 400
        
        # Get the secret from environment variables
        env_secret = os.environ.get('ENV_SECRET')
        if not env_secret:
            return jsonify({
                "status": "error",
                "message": "Server configuration error"
            }), 500
        
        # Compute hash of the environment secret
        expected_hash = hashlib.sha256(env_secret.encode()).hexdigest()
        
        # Compare hashes
        if provided_hash != expected_hash:
            return jsonify({
                "status": "error",
                "message": "Invalid hash"
            }), 403
        
        # If hashes match, proceed to get credentials
        creds = _load_creds(filename, "notion")
        if creds:
            # For Notion credentials, creds is a dict, not a Credentials object
            if isinstance(creds, dict):
                return jsonify({
                    "access_token": creds.get("access_token", ""),
                    "token_type": "bearer",
                    "bot_id": creds.get("bot_id", ""),
                    "workspace_name": creds.get("workspace_name", ""),
                    "workspace_icon": creds.get("workspace_icon"),
                    "workspace_id": creds.get("workspace_id", ""),
                    "owner": creds.get("owner", {
                        "type": "user",
                        "user": {
                            "object": "user",
                            "id": "",
                            "name": "",
                            "avatar_url": "",
                            "type": "person",
                            "person": {
                                "email": ""
                            }
                        }
                    }),
                    "duplicated_template_id": creds.get("duplicated_template_id"),
                    "request_id": creds.get("request_id", "")
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "Invalid credential format for Notion"
                }), 500
        else:
            return jsonify({
                "status": "error",
                "message": f"No credentials found for {filename}"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/pickles')
def list_pickle_files():
    """List all pickle files in the new hierarchical Pickles directory structure"""
    try:
        users_data = {}
        total_files = 0
        
        if PICKLES_DIR.exists():
            # Iterate through user directories
            for user_dir in PICKLES_DIR.iterdir():
                if user_dir.is_dir():
                    user_id = user_dir.name
                    user_files = []
                    
                    # List all pickle files for this user
                    for file in user_dir.iterdir():
                        if file.is_file() and file.suffix == '.pickle':
                            service_name = file.stem  # filename without extension
                            user_files.append({
                                "service": service_name,
                                "filename": file.name,
                                "path": str(file.relative_to(PICKLES_DIR))
                            })
                            total_files += 1
                    
                    if user_files:  # Only include users who have credential files
                        users_data[user_id] = {
                            "services": user_files,
                            "service_count": len(user_files)
                        }
        
        return jsonify({
            "users": users_data,
            "total_users": len(users_data),
            "total_files": total_files,
            "directory": str(PICKLES_DIR),
            "structure": "Pickles/{user_id}/{service}.pickle"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """Root endpoint with basic info"""
    return jsonify({
        "name": "MCP Server with Google OAuth",
        "endpoints": {
            "mcp_sse": "/sse",
            "google_auth": "/google/auth?user_id=<user_id>",
            "health": "/health",
            "pickles": "/pickles"
        }
    })

if __name__ == "__main__":    
    # Run Flask app
    app.run(host="0.0.0.0", port=8000, debug=False)
