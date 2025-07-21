"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Chat Interface Components for the SFC Wizard Agent UI.

This module provides components for the chat interface, including message display,
input handling, and conversation management.
"""

import streamlit as st
from typing import Any, Dict, List, Optional
import time
import re

from sfc_wizard.ui.interface import agent_interface
from sfc_wizard.ui.utils.session import conversation_state, error_handler
from sfc_wizard.ui.utils.formatting import (
    extract_code_blocks,
    format_markdown_text,
    format_code_block,
    format_json,
    format_attachment,
    format_message_content
)
from sfc_wizard.ui.components.config_viewer import config_viewer


def initialize_agent_if_needed() -> bool:
    """
    Initialize the agent if it's not already initialized.
    
    Returns:
        bool: True if the agent is initialized successfully, False otherwise.
    """
    if not agent_interface.is_initialized:
        with st.spinner("Initializing SFC Wizard Agent..."):
            success, error = agent_interface.initialize()
            if not success:
                st.error(f"Failed to initialize agent: {error}")
                return False
    return True


def display_message(message: Dict[str, Any]) -> None:
    """
    Display a message in the chat interface with proper formatting.
    
    Args:
        message (Dict[str, Any]): The message to display.
    """
    role = message.get("role", "user")
    content = message.get("content", "")
    attachments = message.get("attachments", [])
    
    # Use the appropriate icon based on the role
    icon = "👤" if role == "user" else "🏭"
    
    with st.chat_message(role, avatar=icon):
        # Process the content to extract and format code blocks
        formatted_text, code_blocks = format_message_content(content)
        
        # Check if the formatted text contains any code block placeholders
        has_placeholders = any(f"__CODE_BLOCK_{i}__" in formatted_text for i in range(len(code_blocks)))
        
        if has_placeholders:
            # If there are placeholders, display the text and replace placeholders with code blocks
            parts = formatted_text
            for i, block in enumerate(code_blocks):
                placeholder = f"__CODE_BLOCK_{i}__"
                if placeholder in parts:
                    # Split by the placeholder
                    text_parts = parts.split(placeholder, 1)
                    
                    # Display the text before the placeholder
                    if text_parts[0]:
                        st.markdown(text_parts[0])
                    
                    # Display the code block
                    language = block["language"]
                    code = block["code"]
                    st.code(code, language=language)
                    
                    # Update parts to be the remaining text
                    parts = text_parts[1]
            
            # Display any remaining text
            if parts:
                st.markdown(parts)
        else:
            # If there are no placeholders, display the formatted text first
            st.markdown(formatted_text)
            
            # Then display all code blocks
            for block in code_blocks:
                language = block["language"]
                code = block["code"]
                st.code(code, language=language)
        
        # Display attachments if any
        if attachments:
            # Add a separator before attachments
            st.divider()
            
            for attachment in attachments:
                # Format the attachment
                formatted_attachment = format_attachment(attachment)
                attachment_type = formatted_attachment.get("type", "")
                attachment_content = formatted_attachment.get("content", "")
                formatted_content = formatted_attachment.get("formatted_content", "")
                attachment_metadata = formatted_attachment.get("metadata", {})
                
                # Create an expander for the attachment
                name = attachment_metadata.get("name", attachment_type.capitalize())
                with st.expander(f"{name}", expanded=True):
                    # Display the attachment based on its type
                    if attachment_type == "config":
                        try:
                            # Try to display as JSON
                            st.json(attachment_content)
                        except:
                            # Fall back to code display
                            st.code(formatted_content, language="json")
                            
                        # Add download button for the configuration
                        st.download_button(
                            label="Download Configuration",
                            data=formatted_content,
                            file_name=f"{name.lower().replace(' ', '_')}.json",
                            mime="application/json"
                        )
                        
                        # Add button to view in configuration viewer
                        if st.button(f"View in Configuration Viewer", key=f"view_config_{message.get('id', '')}_{name}"):
                            # Add the configuration to the config viewer
                            config_viewer.add_configuration(attachment_content, name=name)
                            # Show a success message
                            st.success(f"Configuration added to the Configuration Viewer!")
                            # Rerun to update the UI
                            st.rerun()
                    elif attachment_type == "visualization":
                        # For now, just display as code. Will be enhanced in Task 5.
                        st.code(formatted_content, language="json")
                    elif attachment_type == "log":
                        st.code(formatted_content, language="text")
                        
                        # Add download button for logs
                        st.download_button(
                            label="Download Log",
                            data=formatted_content,
                            file_name=f"{name.lower().replace(' ', '_')}.log",
                            mime="text/plain"
                        )
                    else:
                        # Default display for unknown attachment types
                        st.text(formatted_content)


def display_conversation_history() -> None:
    """
    Display the entire conversation history.
    """
    messages = conversation_state.get_messages()
    for message in messages:
        display_message(message)


def simulate_typing(placeholder, text: str, speed: float = 0.01) -> None:
    """
    Simulate typing effect for the agent's response.
    
    Args:
        placeholder: Streamlit placeholder to update.
        text (str): The text to display.
        speed (float, optional): The typing speed. Defaults to 0.01.
    """
    # Extract code blocks first to avoid breaking them during typing simulation
    processed_text, code_blocks = extract_code_blocks(text)
    
    # Display the text with a typing effect
    full_text = ""
    for i in range(len(processed_text)):
        full_text += processed_text[i]
        placeholder.markdown(full_text + "▌")
        time.sleep(speed)
    
    # Display the final text without cursor
    placeholder.markdown(processed_text)
    
    # Display code blocks
    for i, block in enumerate(code_blocks):
        language = block["language"]
        code = block["code"]
        st.code(code, language=language)


def process_user_input(user_input: str) -> None:
    """
    Process user input and get agent response.
    
    Args:
        user_input (str): The user's input message.
    """
    if not user_input.strip():
        return
    
    # Add user message to conversation
    conversation_state.add_message(content=user_input, role="user")
    
    # Initialize agent if needed
    if not initialize_agent_if_needed():
        return
    
    # Create a placeholder for the assistant's response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...")
        
        # Send message to agent
        success, response, error = agent_interface.send_message(user_input)
        
        if not success:
            message_placeholder.empty()
            error_handler.handle_agent_error(error or "Unknown error", conversation_state)
            return
        
        # Process the response
        processed_response = agent_interface.process_response(response)
        
        # Clear the placeholder and simulate typing for a more natural feel
        message_placeholder.empty()
        
        # Create a new container for the response with attachments
        response_container = st.container()
        with response_container:
            # Simulate typing for the text response
            text_placeholder = st.empty()
            simulate_typing(text_placeholder, processed_response["text"])
            
            # Display attachments if any
            for attachment in processed_response["attachments"]:
                formatted_attachment = format_attachment(attachment)
                attachment_type = formatted_attachment.get("type", "")
                attachment_content = formatted_attachment.get("content", "")
                formatted_content = formatted_attachment.get("formatted_content", "")
                attachment_metadata = formatted_attachment.get("metadata", {})
                
                # Display a header for the attachment
                name = attachment_metadata.get("name", attachment_type.capitalize())
                st.markdown(f"**{name}:**")
                
                # Display the attachment based on its type
                if attachment_type == "config":
                    try:
                        st.json(attachment_content)
                    except:
                        st.code(formatted_content, language="json")
                elif attachment_type == "visualization":
                    st.code(formatted_content, language="json")
                elif attachment_type == "log":
                    st.code(formatted_content, language="text")
                else:
                    st.text(formatted_content)
    
    # Add agent response to conversation
    conversation_state.add_message(
        content=processed_response["text"],
        role="assistant",
        attachments=processed_response["attachments"]
    )


def render_chat_interface() -> None:
    """
    Render the complete chat interface.
    """
    # Display conversation history
    display_conversation_history()
    
    # Display error if any
    if conversation_state.has_error():
        st.error(conversation_state.get_error())
        if st.button("Clear Error"):
            conversation_state.clear_error()
    
    # Chat input
    user_input = st.chat_input("Type your message here...")
    if user_input:
        process_user_input(user_input)
        # Force a rerun to update the UI with the new messages
        st.rerun()


def render_chat_controls() -> None:
    """
    Render chat control buttons.
    """
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    
    if is_mobile:
        # Stack buttons vertically on mobile for better touch targets
        if st.button("Clear Conversation", use_container_width=True):
            conversation_state.clear_conversation()
            st.rerun()
        
        if st.button("Reinitialize Agent", use_container_width=True):
            agent_interface.shutdown()
            initialize_agent_if_needed()
            st.success("Agent reinitialized successfully!")
    else:
        # Use columns for desktop layout
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear Conversation"):
                conversation_state.clear_conversation()
                st.rerun()
        
        with col2:
            if st.button("Reinitialize Agent"):
                agent_interface.shutdown()
                initialize_agent_if_needed()
                st.success("Agent reinitialized successfully!")