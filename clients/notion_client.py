"""
Gmail API client for the MCP server.
"""

import os
import subprocess
import sys
import base64
import json
import pickle
from pathlib import Path
from urllib.parse import urlencode
import webbrowser
import threading
import time
import logging

from dotenv import load_dotenv
from flask import Flask, redirect, request, url_for
from notion_client import Client

class NotionClient:
    def __init__(self, token_path: str):
        self.token_path = token_path
        self.user_data = None
        
        # Suppress ALL logging output from various sources
        logging.getLogger().setLevel(logging.ERROR)
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('flask').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        logging.getLogger('requests').setLevel(logging.ERROR)
        
        # Suppress warnings
        import warnings
        warnings.filterwarnings('ignore')
        
        # Initialize Flask app with minimal output
        self.app = Flask(__name__)
        
        # Configuration
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)

        self.CLIENT_ID = None
        self.CLIENT_SECRET = None
        self.REDIRECT_URI = None
        self.auth_url = None

        with open(os.path.join(SCRIPT_DIR, '../credentials_notion.json')) as f:
            keys = json.load(f)
            self.CLIENT_ID = keys.get('client_id')
            self.CLIENT_SECRET = keys.get('client_secret') 
            self.REDIRECT_URI = keys.get('redirect_uri')
            self.auth_url = keys.get('auth_url')

        self.NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
        self.NOTION_API_VERSION = "2022-06-28"
        
        # Load existing token if available
        self.user_data = self.load_token()
        
        # Setup routes
        if not self.user_data:
            self.setup_routes()
            self.authenticate()
    
    def build_oauth_url(self, state: str = "init") -> str:
        return self.auth_url

    def save_token(self, data: dict) -> None:
        """Persist token data locally using pickle."""
        try:
            with open(self.token_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception:
            # If we can't write to file, just store in memory
            pass

    def load_token(self) -> dict | None:
        """Load token data from pickle file."""
        
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None
    
    def setup_routes(self):
        """Setup Flask routes for OAuth flow."""
        
        @self.app.route("/")
        def index():
            token = self.user_data or self.load_token()
            if token:
                return (
                    f"<p>Token already stored. You may close this window"
                    f"<h3>User Data:</h3>"
                    f"<pre>{json.dumps(token, indent=2)}</pre>"
                )
            return (
                "<h3>Connect your Notion workspace</h3>"
                f'<a href="/authorize">Add to Notion</a>'
            )

        @self.app.route("/authorize")
        def authorize():
            """Redirect the user to Notion's consent screen."""
            return redirect(self.build_oauth_url())

        @self.app.route("/auth/notion/callback")
        def oauth_callback():
            """Handle Notion redirect → exchange `code` for `access_token`."""
            # Capture `code` param
            code = request.args.get("code")
            if not code:
                return f"Error: {request.args}", 400

            # Prepare Basic Auth header
            basic = base64.b64encode(f"{self.CLIENT_ID}:{self.CLIENT_SECRET}".encode()).decode()

            # Exchange code for token
            import requests  # kept local to avoid an extra dependency in requirements
            res = requests.post(
                self.NOTION_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/json",
                    "Notion-Version": self.NOTION_API_VERSION,
                },
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.REDIRECT_URI,
                },
                timeout=10,
            )
            if not res.ok:
                return f"Token exchange failed → {res.text}", 400

            self.user_data = res.json()
            self.save_token(self.user_data)  # Try to persist, but continue if it fails
            
            # Schedule server shutdown after response is sent
            def shutdown_server():
                time.sleep(2)  # Give time for response to be sent
                try:
                    # Try to shutdown Flask server gracefully
                    func = request.environ.get('werkzeug.server.shutdown')
                    if func is None:
                        # If that doesn't work, use signal
                        import signal
                        os.kill(os.getpid(), signal.SIGTERM)
                    else:
                        func()
                except:
                    # Fallback method
                    import sys
                    sys.exit(0)
            
            threading.Thread(target=shutdown_server, daemon=True).start()

            return (
                f"<p>Authorization complete! You may close this tab now.</p>"
                f"<h3>User Data:</h3>"
                f"<pre>{json.dumps(self.user_data, indent=2)}</pre>"
                # '<a href="/create_page">Create "Hello World" page ↗︎</a></p>'
            )
    
    def open_browser(self):
        """Open the browser to the OAuth server after a short delay."""
        time.sleep(1.5)  # Wait for server to start
        webbrowser.open('http://localhost:8082/')
    
    def authenticate(self):
        threading.Thread(target=self.open_browser, daemon=True).start()
        
        def run_server():
            self.app.run(port=8082, debug=False, use_reloader=False, threaded=True)
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Don't block here - let __init__ complete
        # The server will run in the background until OAuth completes
    
    def get_all_pages(self, top_level_only: bool = False, page_size: int = 100):
        """Retrieve top-level pages from Notion workspace."""
        if not self.user_data or 'access_token' not in self.user_data:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            client = Client(auth=self.user_data["access_token"], notion_version=self.NOTION_API_VERSION)
            
            # Search for pages that are not in databases (top-level pages)
            results = client.search(
                filter={
                    "value": "page",
                    "property": "object"
                },
                page_size=page_size
            )
            
            pages = []
            for page in results.get("results", []):
                # Filter based on top_level_only parameter
                if top_level_only:
                    # Only include workspace pages (top-level pages)
                    if page.get("parent", {}).get("type") == "workspace":
                        pages.append({
                            "id": page.get("id"),
                            "title": self._extract_page_title(page),
                            "url": page.get("url"),
                            "created_time": page.get("created_time"),
                            "last_edited_time": page.get("last_edited_time"),
                            "created_by": page.get("created_by", {}).get("name", "Unknown"),
                            "last_edited_by": page.get("last_edited_by", {}).get("name", "Unknown"),
                            "archived": page.get("archived", False)
                        })
                else:
                    # Include all pages (workspace pages and child pages)
                    pages.append({
                        "id": page.get("id"),
                        "title": self._extract_page_title(page),
                        "url": page.get("url"),
                        "created_time": page.get("created_time"),
                        "last_edited_time": page.get("last_edited_time"),
                        "created_by": page.get("created_by", {}).get("name", "Unknown"),
                        "last_edited_by": page.get("last_edited_by", {}).get("name", "Unknown"),
                        "archived": page.get("archived", False),
                        "parent_type": page.get("parent", {}).get("type", "unknown")
                    })
            
            return {
                "success": True,
                "total_pages": len(pages),
                "pages": pages
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def _extract_page_title(self, page):
        """Extract the title from a Notion page object."""
        try:
            properties = page.get("properties", {})
            
            # Look for title property (could be named differently)
            for prop_name, prop_data in properties.items():
                if prop_data.get("type") == "title":
                    title_array = prop_data.get("title", [])
                    if title_array:
                        return "".join([text.get("plain_text", "") for text in title_array])
            
            # If no title found, return "Untitled"
            return "Untitled"
            
        except Exception:
            return "Err"
    
    def find_page_by_title(self, title: str):
        """Find a page by its title."""
        if not self.user_data or 'access_token' not in self.user_data:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            client = Client(auth=self.user_data["access_token"], notion_version=self.NOTION_API_VERSION)
            
            # Search for pages with the given title
            results = client.search(
                query=title,
                filter={
                    "value": "page",
                    "property": "object"
                }
            )
            
            # Find exact title match
            for page in results.get("results", []):
                page_title = self._extract_page_title(page)
                if page_title.lower() == title.lower():
                    return page.get("id")
            
            return None
            
        except Exception:
            return None
    
    def create_page(self, title: str = None, parent_page_title: str = None, body_content: str = None):
        """Create a new page in Notion."""
        if not self.user_data or 'access_token' not in self.user_data:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            client = Client(auth=self.user_data["access_token"], notion_version=self.NOTION_API_VERSION)
            
            # Set default title if not provided
            if not title:
                title = "New Page"
            
            # Determine parent
            parent = {"type": "workspace", "workspace": True}  # Default to workspace (top-level)
            
            if parent_page_title:
                parent_page_id = self.find_page_by_title(parent_page_title)
                if parent_page_id:
                    parent = {"type": "page_id", "page_id": parent_page_id}
                else:
                    # If parent not found, still create as top-level but note in response
                    pass
            
            # Prepare page properties
            properties = {
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": title}
                        }
                    ]
                }
            }
            
            # Prepare children (body content)
            children = []
            if body_content:
                # Split content into paragraphs
                paragraphs = body_content.split('\n\n')
                for paragraph in paragraphs:
                    if paragraph.strip():
                        children.append({
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": paragraph.strip()}
                                    }
                                ]
                            }
                        })
            
            # Create the page
            new_page = client.pages.create(
                parent=parent,
                properties=properties,
                children=children if children else None
            )
            
            return {
                "success": True,
                "page_id": new_page.get("id"),
                "title": title,
                "url": new_page.get("url"),
                "parent_found": parent_page_title is None or parent.get("type") == "page_id",
                "parent_type": "workspace" if parent.get("type") == "workspace" else "page",
                "created_time": new_page.get("created_time")
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }