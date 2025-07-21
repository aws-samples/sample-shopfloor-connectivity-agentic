"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Response Formatting Utilities for the SFC Wizard Agent UI.

This module provides utilities for formatting agent responses for display in the UI,
including markdown rendering, code block handling, and message type formatting.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
import json

def extract_code_blocks(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Extract code blocks from markdown text.
    
    Args:
        text (str): The markdown text.
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: The text with code blocks replaced by placeholders,
            and a list of extracted code blocks with their languages.
    """
    # Regular expression to match code blocks with better handling of language and content
    pattern = r"```([\w+-]*)\n?(.*?)```"
    code_blocks = []
    
    def replace_code_block(match):
        language = match.group(1).strip() or "text"
        code = match.group(2)
        
        # Map common language aliases to their proper names for syntax highlighting
        language_map = {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "sh": "bash",
            "yml": "yaml",
            "json5": "json",
            "jsonc": "json"
        }
        
        # Use the mapped language if available
        language = language_map.get(language, language)
        
        placeholder = f"__CODE_BLOCK_{len(code_blocks)}__"
        code_blocks.append({"language": language, "code": code})
        return placeholder
    
    # Replace code blocks with placeholders
    processed_text = re.sub(pattern, replace_code_block, text, flags=re.DOTALL)
    
    return processed_text, code_blocks


def format_markdown_text(text: str) -> str:
    """
    Format markdown text for display in the UI.
    
    Args:
        text (str): The markdown text.
        
    Returns:
        str: The formatted text.
    """
    # Process any special markdown formatting if needed
    return text


def format_code_block(code: str, language: str) -> str:
    """
    Format a code block for display in the UI.
    
    Args:
        code (str): The code.
        language (str): The programming language.
        
    Returns:
        str: The formatted code.
    """
    # Remove trailing whitespace and normalize line endings
    code = "\n".join(line.rstrip() for line in code.splitlines())
    return code


def format_json(json_data: Union[Dict[str, Any], List[Any], str]) -> str:
    """
    Format JSON data for display in the UI.
    
    Args:
        json_data (Union[Dict[str, Any], List[Any], str]): The JSON data.
        
    Returns:
        str: The formatted JSON string.
    """
    try:
        # If json_data is a string, try to parse it
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        # Format the JSON with indentation
        return json.dumps(json_data, indent=2)
    except Exception:
        # If parsing fails, return the original data
        if isinstance(json_data, str):
            return json_data
        return str(json_data)


def format_attachment(attachment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format an attachment for display in the UI.
    
    Args:
        attachment (Dict[str, Any]): The attachment data.
        
    Returns:
        Dict[str, Any]: The formatted attachment.
    """
    attachment_type = attachment.get("type", "")
    attachment_content = attachment.get("content", "")
    
    if attachment_type == "config" and isinstance(attachment_content, (dict, list)):
        attachment["formatted_content"] = format_json(attachment_content)
    elif attachment_type == "visualization" and isinstance(attachment_content, (dict, list)):
        attachment["formatted_content"] = format_json(attachment_content)
    elif attachment_type == "log" and isinstance(attachment_content, str):
        attachment["formatted_content"] = attachment_content
    else:
        attachment["formatted_content"] = str(attachment_content)
    
    return attachment


def format_message_content(content: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Format message content for display in the UI.
    
    Args:
        content (str): The message content.
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: The formatted content and extracted code blocks.
    """
    # Extract code blocks
    processed_text, code_blocks = extract_code_blocks(content)
    
    # Format the markdown text
    formatted_text = format_markdown_text(processed_text)
    
    # Format the code blocks
    formatted_code_blocks = []
    for block in code_blocks:
        formatted_code_blocks.append({
            "language": block["language"],
            "code": format_code_block(block["code"], block["language"])
        })
    
    return formatted_text, formatted_code_blocks