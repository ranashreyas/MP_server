"""
Google Drive API client for the MCP server.
"""

import os
import pickle
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io

class DriveClient:
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        
        # Load existing credentials
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"credentials.json not found at {self.credentials_path}. Please download it from Google Cloud Console and place it in the same directory as this script."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, [
                        'https://www.googleapis.com/auth/drive.readonly',
                        'https://www.googleapis.com/auth/drive.metadata.readonly'
                    ])
                try:
                    creds = flow.run_local_server(port=8083, timeout_seconds=300)
                except:
                    # Force cleanup if something goes wrong
                    pass
            
            # Save credentials for next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
    
    def get_service(self):
        """Get Google Drive service instance."""
        if not self.service:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        return self.service
    
    def get_file_editors(self, file_id: str) -> Set[str]:
        """Get all users who have edited a file.
        
        Args:
            file_id: ID of the file to get editors for
        """
        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='owners, lastModifyingUser'
            ).execute()
            
            # Get file revisions
            revisions = self.service.revisions().list(
                fileId=file_id,
                fields='revisions(lastModifyingUser)'
            ).execute()
            
            # Collect all editors
            editors = set()
            
            # Add owners
            for owner in file.get("owners", []):
                if "emailAddress" in owner:
                    editors.add(owner["emailAddress"])
            
            # Add last modifying user
            if "lastModifyingUser" in file and "emailAddress" in file["lastModifyingUser"]:
                editors.add(file["lastModifyingUser"]["emailAddress"])
            
            # Add users from revisions
            for revision in revisions.get("revisions", []):
                if "lastModifyingUser" in revision and "emailAddress" in revision["lastModifyingUser"]:
                    editors.add(revision["lastModifyingUser"]["emailAddress"])
            
            return editors
            
        except Exception:
            return set()
    
    def list_files(self, query: str = None, page_size: int = 100) -> Dict[str, Any]:
        """List files in Google Drive.
        
        Args:
            query: Optional search query (e.g., "name contains 'report'")
            page_size: Maximum number of files to return
        """
        try:
            # Build query
            search_query = []
            if query:
                search_query.append(query)
            search_query.append("trashed = false")
            
            # Execute search
            results = self.service.files().list(
                q=" and ".join(search_query),
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, owners, shared, webViewLink, lastModifyingUser)"
            ).execute()
            
            files = results.get('files', [])
            processed_files = []
            
            for file in files:
                file_id = file.get("id")
                editors = self.get_file_editors(file_id)
                
                processed_files.append({
                    "id": file.get("id"),
                    "name": file.get("name"),
                    "type": file.get("mimeType"),
                    "size": file.get("size"),
                    "created_time": file.get("createdTime"),
                    "modified_time": file.get("modifiedTime"),
                    "owners": [owner.get("emailAddress") for owner in file.get("owners", [])],
                    "shared": file.get("shared", False),
                    "url": file.get("webViewLink"),
                    "last_modified_by": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "editors": list(editors)
                })
            
            return {
                "success": True,
                "total_files": len(processed_files),
                "files": processed_files
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_files(self, query: str, page_size: int = 100) -> Dict[str, Any]:
        """Search for files in Google Drive.
        
        Args:
            query: Search query (e.g., "report" or "meeting notes")
            page_size: Maximum number of files to return
        """
        try:
            # Build search query
            search_query = [
                f"name contains '{query}'",
                "trashed = false"
            ]
            
            # Execute search
            results = self.service.files().list(
                q=" and ".join(search_query),
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, owners, shared, webViewLink, lastModifyingUser)"
            ).execute()
            
            files = results.get('files', [])
            processed_files = []
            
            for file in files:
                file_id = file.get("id")
                editors = self.get_file_editors(file_id)
                
                processed_files.append({
                    "id": file.get("id"),
                    "name": file.get("name"),
                    "type": file.get("mimeType"),
                    "size": file.get("size"),
                    "created_time": file.get("createdTime"),
                    "modified_time": file.get("modifiedTime"),
                    "owners": [owner.get("emailAddress") for owner in file.get("owners", [])],
                    "shared": file.get("shared", False),
                    "url": file.get("webViewLink"),
                    "last_modified_by": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "editors": list(editors)
                })
            
            return {
                "success": True,
                "query": query,
                "total_files": len(processed_files),
                "files": processed_files
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def download_file(self, file_id: str, output_path: str) -> Dict[str, Any]:
        """Download a file from Google Drive.
        
        Args:
            file_id: ID of the file to download
            output_path: Path where the file should be saved
        """
        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, lastModifyingUser'
            ).execute()
            
            # Get editors
            editors = self.get_file_editors(file_id)
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Save file
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            return {
                "success": True,
                "file": {
                    "id": file.get("id"),
                    "name": file.get("name"),
                    "type": file.get("mimeType"),
                    "size": file.get("size"),
                    "saved_to": output_path,
                    "last_modified_by": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "editors": list(editors)
                }
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get detailed metadata for a specific file.
        
        Args:
            file_id: ID of the file to get metadata for
        """
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, createdTime, modifiedTime, owners, shared, webViewLink, description, capabilities, lastModifyingUser'
            ).execute()
            
            # Get editors
            editors = self.get_file_editors(file_id)
            
            return {
                "success": True,
                "file": {
                    "id": file.get("id"),
                    "name": file.get("name"),
                    "type": file.get("mimeType"),
                    "size": file.get("size"),
                    "created_time": file.get("createdTime"),
                    "modified_time": file.get("modifiedTime"),
                    "owners": [owner.get("emailAddress") for owner in file.get("owners", [])],
                    "shared": file.get("shared", False),
                    "url": file.get("webViewLink"),
                    "description": file.get("description"),
                    "capabilities": file.get("capabilities"),
                    "last_modified_by": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "editors": list(editors)
                }
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_shared_files(self, page_size: int = 100) -> Dict[str, Any]:
        """List files that have been shared with the user.
        
        Args:
            page_size: Maximum number of files to return
        """
        try:
            # Build query for shared files
            search_query = [
                "sharedWithMe = true",
                "trashed = false"
            ]
            
            # Execute search
            results = self.service.files().list(
                q=" and ".join(search_query),
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, owners, shared, webViewLink, lastModifyingUser)"
            ).execute()
            
            files = results.get('files', [])
            processed_files = []
            
            for file in files:
                file_id = file.get("id")
                editors = self.get_file_editors(file_id)
                
                processed_files.append({
                    "id": file.get("id"),
                    "name": file.get("name"),
                    "type": file.get("mimeType"),
                    "size": file.get("size"),
                    "created_time": file.get("createdTime"),
                    "modified_time": file.get("modifiedTime"),
                    "owners": [owner.get("emailAddress") for owner in file.get("owners", [])],
                    "shared": file.get("shared", False),
                    "url": file.get("webViewLink"),
                    "last_modified_by": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "editors": list(editors)
                })
            
            return {
                "success": True,
                "total_files": len(processed_files),
                "files": processed_files
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_file_activity(self, file_id: str, max_results: int = 100) -> Dict[str, Any]:
        """Get activity history for a file.
        
        Args:
            file_id: ID of the file to get activity for
            max_results: Maximum number of activities to return
        """
        try:
            # Get file metadata first
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, createdTime, modifiedTime, owners, lastModifyingUser'
            ).execute()
            
            # Get file revisions
            revisions = self.service.revisions().list(
                fileId=file_id,
                fields='revisions(id, modifiedTime, keepForever, originalFilename, mimeType, lastModifyingUser)'
            ).execute()
            
            # Process revisions into activity history
            activities = []
            
            # Add creation activity
            activities.append({
                "type": "created",
                "time": file.get("createdTime"),
                "user": file.get("owners", [{}])[0].get("emailAddress"),
                "details": "File created"
            })
            
            # Add modification activities from revisions
            for revision in revisions.get("revisions", []):
                activities.append({
                    "type": "modified",
                    "time": revision.get("modifiedTime"),
                    "user": revision.get("lastModifyingUser", {}).get("emailAddress"),
                    "details": f"File modified (revision {revision.get('id')})"
                })
            
            # Sort activities by time
            activities.sort(key=lambda x: x["time"], reverse=True)
            
            # Get all editors
            editors = self.get_file_editors(file_id)
            
            return {
                "success": True,
                "file": {
                    "id": file.get("id"),
                    "name": file.get("name"),
                    "created_time": file.get("createdTime"),
                    "modified_time": file.get("modifiedTime"),
                    "owners": [owner.get("emailAddress") for owner in file.get("owners", [])],
                    "last_modified_by": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "editors": list(editors)
                },
                "total_activities": len(activities),
                "activities": activities[:max_results]
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_recent_activity(self, max_results: int = 100) -> Dict[str, Any]:
        """Get recent activity across all accessible files.
        
        Args:
            max_results: Maximum number of activities to return
        """
        try:
            # Get recently modified files
            results = self.service.files().list(
                orderBy="modifiedTime desc",
                pageSize=max_results,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, lastModifyingUser)"
            ).execute()
            
            files = results.get('files', [])
            activities = []
            
            for file in files:
                file_id = file.get("id")
                editors = self.get_file_editors(file_id)
                
                activities.append({
                    "type": "modified",
                    "time": file.get("modifiedTime"),
                    "user": file.get("lastModifyingUser", {}).get("emailAddress"),
                    "file": {
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": file.get("mimeType"),
                        "editors": list(editors)
                    },
                    "details": "File modified"
                })
            
            return {
                "success": True,
                "total_activities": len(activities),
                "activities": activities
            }
            
        except HttpError as error:
            return {
                "success": False,
                "error": str(error)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            } 