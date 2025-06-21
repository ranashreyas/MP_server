"""
Notion Block Models and Parsers

This module provides classes and functions to create Notion block objects
according to the Notion API specification.
"""

import re
from typing import List, Dict, Any, Optional, Union
from enum import Enum


class BlockType(Enum):
    """Enumeration of Notion block types."""
    PARAGRAPH = "paragraph"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    TO_DO = "to_do"
    TOGGLE = "toggle"
    QUOTE = "quote"
    CODE = "code"
    DIVIDER = "divider"
    CALLOUT = "callout"
    TABLE = "table"
    TABLE_ROW = "table_row"


class RichText:
    """Represents rich text content in Notion blocks."""
    
    def __init__(self, content: str, annotations: Optional[Dict[str, Any]] = None, link: Optional[str] = None):
        self.content = content
        self.annotations = annotations or {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default"
        }
        self.link = link
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Notion API format."""
        return {
            "type": "text",
            "text": {
                "content": self.content,
                "link": self.link
            },
            "annotations": self.annotations,
            "plain_text": self.content,
            "href": self.link
        }


class Block:
    """Base class for Notion blocks."""
    
    def __init__(self, block_type: BlockType, rich_text: List[RichText] = None, 
                 color: str = "default", children: List['Block'] = None):
        self.block_type = block_type
        self.rich_text = rich_text or []
        self.color = color
        self.children = children or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert block to Notion API format."""
        block_dict = {
            "object": "block",
            "type": self.block_type.value,
            self.block_type.value: {
                "rich_text": [rt.to_dict() for rt in self.rich_text],
                "color": self.color
            }
        }
        
        # Add children if present
        if self.children:
            block_dict[self.block_type.value]["children"] = [child.to_dict() for child in self.children]
        
        return block_dict


class ParagraphBlock(Block):
    """Paragraph block."""
    def __init__(self, rich_text: List[RichText] = None, color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.PARAGRAPH, rich_text, color, children)


class HeadingBlock(Block):
    """Heading block (H1, H2, H3)."""
    def __init__(self, level: int, rich_text: List[RichText] = None, color: str = "default", 
                 is_toggleable: bool = False, children: List[Block] = None):
        if level == 1:
            block_type = BlockType.HEADING_1
        elif level == 2:
            block_type = BlockType.HEADING_2
        elif level == 3:
            block_type = BlockType.HEADING_3
        else:
            raise ValueError("Heading level must be 1, 2, or 3")
        
        super().__init__(block_type, rich_text, color, children)
        self.is_toggleable = is_toggleable
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert heading block to Notion API format."""
        block_dict = super().to_dict()
        block_dict[self.block_type.value]["is_toggleable"] = self.is_toggleable
        return block_dict


class ListItemBlock(Block):
    """Base class for list items."""
    def __init__(self, block_type: BlockType, rich_text: List[RichText] = None, 
                 color: str = "default", children: List[Block] = None):
        super().__init__(block_type, rich_text, color, children)


class BulletedListItemBlock(ListItemBlock):
    """Bulleted list item block."""
    def __init__(self, rich_text: List[RichText] = None, color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.BULLETED_LIST_ITEM, rich_text, color, children)


class NumberedListItemBlock(ListItemBlock):
    """Numbered list item block."""
    def __init__(self, rich_text: List[RichText] = None, color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.NUMBERED_LIST_ITEM, rich_text, color, children)


class ToDoBlock(Block):
    """To-do block."""
    def __init__(self, rich_text: List[RichText] = None, checked: bool = False, 
                 color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.TO_DO, rich_text, color, children)
        self.checked = checked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to-do block to Notion API format."""
        block_dict = super().to_dict()
        block_dict[self.block_type.value]["checked"] = self.checked
        return block_dict


class ToggleBlock(Block):
    """Toggle block."""
    def __init__(self, rich_text: List[RichText] = None, color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.TOGGLE, rich_text, color, children)


class QuoteBlock(Block):
    """Quote block."""
    def __init__(self, rich_text: List[RichText] = None, color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.QUOTE, rich_text, color, children)


class CodeBlock(Block):
    """Code block."""
    def __init__(self, rich_text: List[RichText] = None, language: str = "plain text", 
                 color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.CODE, rich_text, color, children)
        self.language = language
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert code block to Notion API format."""
        block_dict = super().to_dict()
        block_dict[self.block_type.value]["language"] = self.language
        return block_dict


class DividerBlock(Block):
    """Divider block."""
    def __init__(self, color: str = "default"):
        super().__init__(BlockType.DIVIDER, [], color)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert divider block to Notion API format."""
        return {
            "object": "block",
            "type": self.block_type.value,
            self.block_type.value: {
                "color": self.color
            }
        }


class CalloutBlock(Block):
    """Callout block."""
    def __init__(self, rich_text: List[RichText] = None, icon: Optional[Dict[str, Any]] = None,
                 color: str = "default", children: List[Block] = None):
        super().__init__(BlockType.CALLOUT, rich_text, color, children)
        self.icon = icon or {"type": "emoji", "emoji": "💡"}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert callout block to Notion API format."""
        block_dict = super().to_dict()
        block_dict[self.block_type.value]["icon"] = self.icon
        return block_dict


class TableBlock(Block):
    """Table block."""
    def __init__(self, table_width: int, has_column_header: bool = True, has_row_header: bool = False,
                 color: str = "default", children: List['TableRowBlock'] = None):
        super().__init__(BlockType.TABLE, [], color, children)
        self.table_width = table_width
        self.has_column_header = has_column_header
        self.has_row_header = has_row_header
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert table block to Notion API format."""
        return {
            "object": "block",
            "type": self.block_type.value,
            self.block_type.value: {
                "table_width": self.table_width,
                "has_column_header": self.has_column_header,
                "has_row_header": self.has_row_header,
                # "color": self.color,
                "children": [child.to_dict() for child in self.children] if self.children else []
            }
        }


class TableRowBlock(Block):
    """Table row block."""
    def __init__(self, cells: List[List[RichText]], color: str = "default"):
        super().__init__(BlockType.TABLE_ROW, [], color)
        self.cells = cells
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert table row block to Notion API format."""
        return {
            "object": "block",
            "type": self.block_type.value,
            self.block_type.value: {
                "cells": [[rt.to_dict() for rt in cell] for cell in self.cells],
                # "color": self.color
            }
        }


def parse_annotations(text: str) -> tuple[str, Dict[str, Any]]:
    """Parse text annotations and return clean text with annotations."""
    annotations = {
        "bold": False,
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "code": False,
        "color": "default"
    }
    
    # Parse bold (**text**)
    if text.startswith("**") and text.endswith("**") and len(text) > 4:
        annotations["bold"] = True
        text = text[2:-2]
    
    # Parse italic (*text*)
    if text.startswith("*") and text.endswith("*") and len(text) > 2:
        annotations["italic"] = True
        text = text[1:-1]
    
    # Parse strikethrough (~text~)
    if text.startswith("~") and text.endswith("~") and len(text) > 2:
        annotations["strikethrough"] = True
        text = text[1:-1]
    
    # Parse inline code (`text`)
    if text.startswith("`") and text.endswith("`") and len(text) > 2:
        annotations["code"] = True
        text = text[1:-1]
    
    return text, annotations


def parse_table_content(table_content: str) -> List[TableRowBlock]:
    """Parse table content into table row blocks.
    
    Expected format:
    ((col1, col2, col3)(cell1, cell2, cell3)(cell4, cell5, cell6))
    """
    table_rows = []
    
    # Remove outer parentheses
    if table_content.startswith('((') and table_content.endswith('))'):
        table_content = table_content[2:-2]
    else:
        return table_rows
    
    # Split by row parentheses
    rows = table_content.split(')(')
    
    for row in rows:
        # Remove any remaining parentheses
        row = row.strip('()')
        if not row:
            continue
        
        # Split by commas
        cells = [cell.strip() for cell in row.split(',')]
        if cells:
            # Convert each cell to RichText
            rich_text_cells = []
            for cell in cells:
                clean_text, annotations = parse_annotations(cell)
                rich_text_cells.append([RichText(clean_text, annotations)])
            
            table_rows.append(TableRowBlock(rich_text_cells))
    
    return table_rows


def parse_content_to_blocks(content: str) -> List[Block]:
    """Parse markdown-like content into Notion blocks."""
    if not content:
        return []
    
    blocks = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Parse table blocks ((col1, col2, col3)(cell1, cell2, cell3)(cell4, cell5, cell6))
        if line.startswith('((') and line.endswith('))'):
            # Parse table
            table_rows = parse_table_content(line)
            if table_rows:
                # Determine table width from first row
                table_width = len(table_rows[0].cells)
                table_block = TableBlock(table_width=table_width, children=table_rows)
                blocks.append(table_block)
                i += 1
                continue
        
        # Parse headings (# ## ###)
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            if level <= 3:
                text = line[level:].strip()
                rich_text = [RichText(text)]
                blocks.append(HeadingBlock(level, rich_text))
                i += 1
                continue
        
        # Parse to-do items ([] or [x])
        if line.startswith('[]') or line.startswith('[x]'):
            checked = line.startswith('[x]')
            text = line[2:].strip()
            rich_text = [RichText(text)]
            blocks.append(ToDoBlock(rich_text, checked))
            i += 1
            continue
        
        # Parse bulleted lists (* - +)
        if line.startswith(('* ', '- ', '+ ')):
            text = line[2:].strip()
            rich_text = [RichText(text)]
            blocks.append(BulletedListItemBlock(rich_text))
            i += 1
            continue
        
        # Parse numbered lists (1. a. i.)
        numbered_match = re.match(r'^(\d+\.|a\.|i\.)\s+(.+)$', line)
        if numbered_match:
            text = numbered_match.group(2).strip()
            rich_text = [RichText(text)]
            blocks.append(NumberedListItemBlock(rich_text))
            i += 1
            continue
        
        # Parse toggle blocks (>)
        if line.startswith('> '):
            text = line[2:].strip()
            rich_text = [RichText(text)]
            blocks.append(ToggleBlock(rich_text))
            i += 1
            continue
        
        # Parse quote blocks (")
        if line.startswith('" '):
            text = line[2:].strip()
            rich_text = [RichText(text)]
            blocks.append(QuoteBlock(rich_text))
            i += 1
            continue
        
        # Parse dividers (---)
        if line == '---':
            blocks.append(DividerBlock())
            i += 1
            continue
        
        # Parse callouts (💡 or other emoji)
        if re.match(r'^[💡💭💬💡🔍⚠️✅❌]\s+(.+)$', line):
            emoji = line[0]
            text = line[2:].strip()
            rich_text = [RichText(text)]
            icon = {"type": "emoji", "emoji": emoji}
            blocks.append(CalloutBlock(rich_text, icon))
            i += 1
            continue
        
        # Default to paragraph
        # Check for multiple lines that should be part of the same paragraph
        paragraph_lines = [line]
        j = i + 1
        while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith(('#', '[]', '[x]', '* ', '- ', '+ ', '> ', '" ', '---', '💡', '💭', '💬', '🔍', '⚠️', '✅', '❌', '((')):
            if not re.match(r'^(\d+\.|a\.|i\.)\s+', lines[j].strip()):
                paragraph_lines.append(lines[j].strip())
                j += 1
            else:
                break
        
        # Join paragraph lines and parse annotations
        paragraph_text = ' '.join(paragraph_lines)
        clean_text, annotations = parse_annotations(paragraph_text)
        rich_text = [RichText(clean_text, annotations)]
        blocks.append(ParagraphBlock(rich_text))
        
        i = j
    
    return blocks


def blocks_to_notion_format(blocks: List[Block]) -> List[Dict[str, Any]]:
    """Convert blocks to Notion API format."""
    return [block.to_dict() for block in blocks] 