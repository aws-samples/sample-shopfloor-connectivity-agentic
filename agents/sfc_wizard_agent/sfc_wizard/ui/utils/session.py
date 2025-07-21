"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Session management utilities for the SFC Wizard Agent UI.

This module provides utilities for managing conversation state and error handling.
"""

import streamlit as st
from typing import Any, Dict, List, Optional, Union
import uuid
import time
import json
import gzip
import base64
import io

class ConversationState:
    """Class for managing conversation state."""
    
    def __init__(self):
        """Initialize the conversation state."""
        # Initialize session state for messages if it doesn't exist
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Initialize session state for error if it doesn't exist
        if "error" not in st.session_state:
            st.session_state.error = None
        
        # Initialize session state for message batches if it doesn't exist
        if "message_batches" not in st.session_state:
            st.session_state.message_batches = []
        
        # Initialize session state for compression settings
        if "compress_messages" not in st.session_state:
            st.session_state.compress_messages = False
    
    def add_message(self, content: str, role: str = "user", attachments: List[Dict[str, Any]] = None) -> str:
        """
        Add a message to the conversation.
        
        Args:
            content (str): The message content.
            role (str, optional): The role of the message sender. Defaults to "user".
            attachments (List[Dict[str, Any]], optional): List of attachments. Defaults to None.
            
        Returns:
            str: The ID of the added message.
        """
        # Generate a unique ID for the message
        message_id = str(uuid.uuid4())
        
        # Create the message object
        message = {
            "id": message_id,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "attachments": attachments or []
        }
        
        # Check if we should use compression for large messages
        should_compress = st.session_state.get("compress_messages", False)
        
        if should_compress and (len(content) > 10000 or (attachments and len(str(attachments)) > 10000)):
            # Compress large messages
            message = self._compress_message(message)
        
        # Add the message to the session state
        st.session_state.messages.append(message)
        
        # Check if we need to batch messages for performance
        if len(st.session_state.messages) > 50:
            self._batch_old_messages()
        
        return message_id
    
    def _compress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress a message to save memory.
        
        Args:
            message (Dict[str, Any]): The message to compress.
            
        Returns:
            Dict[str, Any]: The compressed message.
        """
        # Create a copy of the message
        compressed_message = message.copy()
        
        # Compress the content
        if len(message["content"]) > 10000:
            content_bytes = message["content"].encode('utf-8')
            compressed_content = gzip.compress(content_bytes)
            encoded_content = base64.b64encode(compressed_content).decode('utf-8')
            compressed_message["content"] = f"__COMPRESSED__{encoded_content}"
        
        # Compress attachments if they exist and are large
        if message["attachments"] and len(str(message["attachments"])) > 10000:
            attachments_json = json.dumps(message["attachments"])
            attachments_bytes = attachments_json.encode('utf-8')
            compressed_attachments = gzip.compress(attachments_bytes)
            encoded_attachments = base64.b64encode(compressed_attachments).decode('utf-8')
            compressed_message["attachments"] = [{"type": "__COMPRESSED__", "content": encoded_attachments}]
        
        # Add a flag to indicate that the message is compressed
        compressed_message["compressed"] = True
        
        return compressed_message
    
    def _decompress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompress a message.
        
        Args:
            message (Dict[str, Any]): The compressed message.
            
        Returns:
            Dict[str, Any]: The decompressed message.
        """
        # Check if the message is compressed
        if not message.get("compressed", False):
            return message
        
        # Create a copy of the message
        decompressed_message = message.copy()
        
        # Decompress the content if it's compressed
        if isinstance(message["content"], str) and message["content"].startswith("__COMPRESSED__"):
            encoded_content = message["content"][14:]  # Remove the prefix
            compressed_content = base64.b64decode(encoded_content)
            content_bytes = gzip.decompress(compressed_content)
            decompressed_message["content"] = content_bytes.decode('utf-8')
        
        # Decompress attachments if they're compressed
        if message["attachments"] and len(message["attachments"]) == 1 and message["attachments"][0].get("type") == "__COMPRESSED__":
            encoded_attachments = message["attachments"][0]["content"]
            compressed_attachments = base64.b64decode(encoded_attachments)
            attachments_bytes = gzip.decompress(compressed_attachments)
            decompressed_message["attachments"] = json.loads(attachments_bytes.decode('utf-8'))
        
        # Remove the compression flag
        decompressed_message.pop("compressed", None)
        
        return decompressed_message
    
    def _batch_old_messages(self) -> None:
        """
        Batch old messages to improve performance.
        This keeps the most recent messages in memory and archives older ones.
        """
        # Keep the 30 most recent messages in the active list
        recent_messages = st.session_state.messages[-30:]
        old_messages = st.session_state.messages[:-30]
        
        # Add the old messages to the batches
        if old_messages:
            batch = {
                "id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "messages": old_messages
            }
            st.session_state.message_batches.append(batch)
        
        # Update the active messages
        st.session_state.messages = recent_messages
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages in the conversation.
        
        Returns:
            List[Dict[str, Any]]: The list of messages.
        """
        # Get the active messages
        messages = st.session_state.messages.copy()
        
        # Decompress any compressed messages
        for i, message in enumerate(messages):
            if message.get("compressed", False):
                messages[i] = self._decompress_message(message)
        
        return messages
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific message by ID.
        
        Args:
            message_id (str): The ID of the message.
            
        Returns:
            Optional[Dict[str, Any]]: The message or None if not found.
        """
        # Check active messages
        for message in st.session_state.messages:
            if message["id"] == message_id:
                # Decompress if needed
                if message.get("compressed", False):
                    return self._decompress_message(message)
                return message
        
        # Check batched messages
        for batch in st.session_state.message_batches:
            for message in batch["messages"]:
                if message["id"] == message_id:
                    # Decompress if needed
                    if message.get("compressed", False):
                        return self._decompress_message(message)
                    return message
        
        return None
    
    def clear_conversation(self) -> None:
        """
        Clear the conversation history.
        """
        st.session_state.messages = []
        st.session_state.message_batches = []
    
    def set_error(self, error: str) -> None:
        """
        Set an error message.
        
        Args:
            error (str): The error message.
        """
        st.session_state.error = error
    
    def get_error(self) -> Optional[str]:
        """
        Get the current error message.
        
        Returns:
            Optional[str]: The error message or None if no error.
        """
        return st.session_state.error
    
    def has_error(self) -> bool:
        """
        Check if there is an error.
        
        Returns:
            bool: True if there is an error, False otherwise.
        """
        return st.session_state.error is not None
    
    def clear_error(self) -> None:
        """
        Clear the error message.
        """
        st.session_state.error = None
    
    def enable_compression(self, enable: bool = True) -> None:
        """
        Enable or disable message compression.
        
        Args:
            enable (bool, optional): Whether to enable compression. Defaults to True.
        """
        st.session_state.compress_messages = enable


class ErrorHandler:
    """Class for handling errors in the UI."""
    
    def handle_agent_error(self, error: str, conversation_state: ConversationState) -> None:
        """
        Handle an error from the agent.
        
        Args:
            error (str): The error message.
            conversation_state (ConversationState): The conversation state.
        """
        # Set the error in the conversation state
        conversation_state.set_error(f"Agent Error: {error}")
        
        # Log the error
        print(f"Agent Error: {error}")


# Create singleton instances
conversation_state = ConversationState()
error_handler = ErrorHandler()