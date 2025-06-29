"""
Notion API client for the MCP server.
"""

import os
import pickle
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from notion_client import Client

# Import the block parser
from .notion_models import parse_content_to_blocks, blocks_to_notion_format

class NotionClient:
    def __init__(self, creds: Dict[str, Any]):
        self.creds = creds
        self.service = None
        self.NOTION_API_VERSION = "2022-06-28"        
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Notion API using provided credentials dict."""
        if not isinstance(self.creds, dict):
            raise ValueError(f"Expected credentials dict, got {type(self.creds)}")
        
        # Validate required fields
        required_fields = ['access_token']
        missing_fields = [field for field in required_fields if not self.creds.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required credential fields: {missing_fields}")
        
        # Validate access token exists and is non-empty
        access_token = self.creds.get('access_token')
        if not access_token or not isinstance(access_token, str):
            raise ValueError("Invalid or missing access_token in credentials")
        
        try:
            self.service = Client(auth=access_token, notion_version=self.NOTION_API_VERSION)
            # Test the connection by making a simple API call
            self.service.users.me()
        except Exception as e:
            raise ValueError(f"Failed to authenticate with Notion: {e}")
    
    def get_all_pages(self, top_level_only: bool = False, page_size: int = 100):
        if not self.service:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            # Search for pages that are not in databases (top-level pages)
            results = self.service.search(
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
        if not self.service:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            # Search for pages with the given title
            results = self.service.search(
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
        if not self.service:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
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
            
            # Parse body content into Notion blocks
            children = None
            if body_content:
                # Parse content into blocks using the new parser
                blocks = parse_content_to_blocks(body_content)
                children = blocks_to_notion_format(blocks)
            
            # Create the page
            new_page = self.service.pages.create(
                parent=parent,
                properties=properties,
                children=children
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

    def update_page(self, page_id: str, new_title: str = None, new_content: str = None, append_content: bool = False):
        """Update an existing page in Notion.
        
        Args:
            page_id: Page ID to update
            new_title: New title for the page (optional)
            new_content: New content for the page (optional)
            append_content: If True, append content; if False, replace existing content
        """
        if not self.service:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            # Update title if provided
            if new_title:
                try:
                    self.service.pages.update(
                        page_id=page_id,
                        properties={
                            "title": {
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {"content": new_title}
                                    }
                                ]
                            }
                        }
                    )
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to update title: {str(e)}"
                    }
            
            # Update content if provided
            if new_content:
                try:
                    # If replacing content, first get and delete existing blocks
                    if not append_content:
                        existing_blocks = self.service.blocks.children.list(block_id=page_id)
                        for block in existing_blocks.get("results", []):
                            try:
                                self.service.blocks.delete(block_id=block["id"])
                            except:
                                pass  # Some blocks might not be deletable
                    
                    # Parse new content into Notion blocks using the new parser
                    blocks = parse_content_to_blocks(new_content)
                    new_blocks = blocks_to_notion_format(blocks)
                    
                    # Add new blocks
                    if new_blocks:
                        self.service.blocks.children.append(block_id=page_id, children=new_blocks)
                        
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to update content: {str(e)}"
                    }
            
            # Get updated page info
            try:
                updated_page = self.service.pages.retrieve(page_id=page_id)
                return {
                    "success": True,
                    "page_id": page_id,
                    "title": self._extract_page_title(updated_page),
                    "url": updated_page.get("url"),
                    "last_edited_time": updated_page.get("last_edited_time"),
                    "updates_applied": {
                        "title_updated": new_title is not None,
                        "content_updated": new_content is not None,
                        "content_action": "appended" if append_content else "replaced"
                    }
                }
            except Exception as e:
                return {
                    "success": True,  # Update likely succeeded even if we can't retrieve
                    "page_id": page_id,
                    "message": "Page updated but couldn't retrieve updated info",
                    "updates_applied": {
                        "title_updated": new_title is not None,
                        "content_updated": new_content is not None,
                        "content_action": "appended" if append_content else "replaced"
                    }
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_pages_content(self, page_ids: list[str]):
        """Get content of multiple pages by their IDs.
        
        Args:
            page_ids: List of page IDs to fetch content for
            
        Returns:
            Dictionary containing success status and page contents
        """
        if not self.service:
            raise Exception("Not authenticated. Please complete OAuth flow first.")
        
        try:
            pages_content = []
            for page_id in page_ids:
                try:
                    # Get page metadata
                    page = self.service.pages.retrieve(page_id=page_id)
                    
                    # Get page blocks (content)
                    blocks = self.service.blocks.children.list(block_id=page_id)
                    
                    # Extract text content from blocks
                    content = []
                    for block in blocks.get("results", []):
                        block_type = block.get("type")
                        if block_type == "paragraph":
                            text = "".join([text.get("plain_text", "") for text in block.get("paragraph", {}).get("rich_text", [])])
                            if text:
                                content.append(text)
                        elif block_type == "heading_1":
                            text = "".join([text.get("plain_text", "") for text in block.get("heading_1", {}).get("rich_text", [])])
                            if text:
                                content.append(f"# {text}")
                        elif block_type == "heading_2":
                            text = "".join([text.get("plain_text", "") for text in block.get("heading_2", {}).get("rich_text", [])])
                            if text:
                                content.append(f"## {text}")
                        elif block_type == "heading_3":
                            text = "".join([text.get("plain_text", "") for text in block.get("heading_3", {}).get("rich_text", [])])
                            if text:
                                content.append(f"### {text}")
                        elif block_type == "bulleted_list_item":
                            text = "".join([text.get("plain_text", "") for text in block.get("bulleted_list_item", {}).get("rich_text", [])])
                            if text:
                                content.append(f"• {text}")
                        elif block_type == "numbered_list_item":
                            text = "".join([text.get("plain_text", "") for text in block.get("numbered_list_item", {}).get("rich_text", [])])
                            if text:
                                content.append(f"1. {text}")
                        elif block_type == "to_do":
                            text = "".join([text.get("plain_text", "") for text in block.get("to_do", {}).get("rich_text", [])])
                            checked = block.get("to_do", {}).get("checked", False)
                            if text:
                                content.append(f"[{'x' if checked else ' '}] {text}")
                        elif block_type == "quote":
                            text = "".join([text.get("plain_text", "") for text in block.get("quote", {}).get("rich_text", [])])
                            if text:
                                content.append(f"> {text}")
                    
                    pages_content.append({
                        "id": page_id,
                        "title": self._extract_page_title(page),
                        "url": page.get("url"),
                        "content": "\n".join(content),
                        "last_edited_time": page.get("last_edited_time")
                    })
                    
                except Exception as e:
                    pages_content.append({
                        "id": page_id,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "pages": pages_content
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }