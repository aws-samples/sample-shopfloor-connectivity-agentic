"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Configuration Viewer Component for the SFC Wizard Agent UI.

This module provides components for viewing, downloading, and copying SFC configurations
with syntax highlighting and proper formatting.
"""

import streamlit as st
import json
from typing import Any, Dict, List, Optional, Union
import pyperclip
import uuid

from sfc_wizard.ui.utils.formatting import format_json
from sfc_wizard.ui.utils.session import conversation_state, error_handler


class ConfigurationViewer:
    """Class for viewing and interacting with SFC configurations."""
    
    def __init__(self):
        """Initialize the configuration viewer."""
        # Initialize session state for configurations if it doesn't exist
        if "configurations" not in st.session_state:
            st.session_state.configurations = []
    
    def add_configuration(self, config: Union[Dict[str, Any], List[Any], str], name: str = None) -> str:
        """
        Add a configuration to the session state.
        
        Args:
            config (Union[Dict[str, Any], List[Any], str]): The configuration data.
            name (str, optional): The name of the configuration. Defaults to None.
            
        Returns:
            str: The ID of the added configuration.
        """
        # Generate a unique ID for the configuration
        config_id = str(uuid.uuid4())
        
        # Parse the configuration if it's a string
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                # If parsing fails, keep it as a string
                pass
        
        # Generate a default name if none is provided
        if not name:
            name = f"Configuration {len(st.session_state.configurations) + 1}"
        
        # Add the configuration to the session state
        st.session_state.configurations.append({
            "id": config_id,
            "name": name,
            "config": config,
            "timestamp": st.session_state.get("server_time", "")
        })
        
        return config_id
    
    def get_configurations(self) -> List[Dict[str, Any]]:
        """
        Get all configurations in the session state.
        
        Returns:
            List[Dict[str, Any]]: The list of configurations.
        """
        return st.session_state.configurations
    
    def get_configuration(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific configuration by ID.
        
        Args:
            config_id (str): The ID of the configuration.
            
        Returns:
            Optional[Dict[str, Any]]: The configuration or None if not found.
        """
        for config in st.session_state.configurations:
            if config["id"] == config_id:
                return config
        return None
    
    def clear_configurations(self) -> None:
        """
        Clear all configurations from the session state.
        """
        st.session_state.configurations = []
    
    def render_configuration(self, config: Union[Dict[str, Any], List[Any], str], name: str = None) -> None:
        """
        Render a configuration in the UI.
        
        Args:
            config (Union[Dict[str, Any], List[Any], str]): The configuration data.
            name (str, optional): The name of the configuration. Defaults to None.
        """
        # Generate a default name if none is provided
        if not name:
            name = "Configuration"
        
        # Create an expander for the configuration
        with st.expander(name, expanded=True):
            # Try to display as JSON with syntax highlighting
            try:
                if isinstance(config, str):
                    # Try to parse the string as JSON
                    try:
                        parsed_config = json.loads(config)
                        st.json(parsed_config)
                        formatted_json = format_json(parsed_config)
                    except json.JSONDecodeError:
                        # If parsing fails, display as code
                        st.code(config, language="json")
                        formatted_json = config
                else:
                    # Display as JSON
                    st.json(config)
                    formatted_json = format_json(config)
                
                # Add buttons for downloading, copying, and editing
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Download button
                    st.download_button(
                        label="Download JSON",
                        data=formatted_json,
                        file_name=f"{name.lower().replace(' ', '_')}.json",
                        mime="application/json"
                    )
                
                with col2:
                    # Copy button
                    if st.button(f"Copy to Clipboard", key=f"copy_{uuid.uuid4()}"):
                        try:
                            pyperclip.copy(formatted_json)
                            st.success("Configuration copied to clipboard!")
                        except Exception as e:
                            st.error(f"Failed to copy: {str(e)}")
                
                with col3:
                    # Edit button - we'll use session state to track which configuration to edit
                    if st.button(f"Edit Configuration", key=f"edit_{uuid.uuid4()}"):
                        # Store the configuration ID in session state
                        if "config_to_edit" not in st.session_state:
                            st.session_state.config_to_edit = {}
                        
                        # Store the configuration data
                        if isinstance(config, str):
                            try:
                                config_data = json.loads(config)
                            except json.JSONDecodeError:
                                config_data = config
                        else:
                            config_data = config
                        
                        # Add to session state
                        config_id = str(uuid.uuid4())
                        st.session_state.config_to_edit = {
                            "id": config_id,
                            "config": config_data,
                            "name": name
                        }
                        
                        # Add to configurations if not already there
                        self.add_configuration(config_data, name=name)
                        
                        # Switch to the edit tab
                        st.session_state.active_tab = "Edit Configuration"
                        
                        # Rerun to update the UI
                        st.rerun()
            
            except Exception as e:
                # If JSON display fails, show an error
                st.error(f"Failed to display configuration: {str(e)}")
                # Try to display as text
                st.text(str(config))
    
    def render_configuration_list(self) -> None:
        """
        Render a list of all configurations in the session state.
        """
        configurations = self.get_configurations()
        
        if not configurations:
            st.info("No configurations available. Use the chat to generate configurations or upload a configuration file.")
            return
        
        # Add a button to clear all configurations
        if st.button("Clear All Configurations"):
            self.clear_configurations()
            st.rerun()
        
        # Display each configuration
        for config in configurations:
            self.render_configuration(config["config"], config["name"])
    
    def render_configuration_upload(self) -> None:
        """
        Render a file uploader for configurations.
        """
        uploaded_file = st.file_uploader("Upload a configuration file", type=["json"])
        
        if uploaded_file is not None:
            try:
                # Read and parse the uploaded file
                content = uploaded_file.read()
                config = json.loads(content)
                
                # Add the configuration to the session state
                self.add_configuration(config, name=uploaded_file.name)
                
                # Show a success message
                st.success(f"Configuration '{uploaded_file.name}' uploaded successfully!")
                
                # Rerun to update the UI
                st.rerun()
            
            except json.JSONDecodeError:
                st.error("Invalid JSON file. Please upload a valid JSON configuration.")
            except Exception as e:
                st.error(f"Failed to upload configuration: {str(e)}")


# Create a singleton instance of the configuration viewer
config_viewer = ConfigurationViewer()


def render_config_viewer() -> None:
    """
    Render the complete configuration viewer interface.
    """
    st.header("⚙️ Configuration Viewer")
    
    # Add tabs for different sections
    tab1, tab2 = st.tabs(["View Configurations", "Upload Configuration"])
    
    with tab1:
        # Render the list of configurations
        config_viewer.render_configuration_list()
    
    with tab2:
        # Render the configuration upload interface
        config_viewer.render_configuration_upload()


def extract_configurations_from_messages() -> None:
    """
    Extract configurations from the conversation history and add them to the configuration viewer.
    """
    messages = conversation_state.get_messages()
    
    for message in messages:
        # Check if the message has attachments
        attachments = message.get("attachments", [])
        
        for attachment in attachments:
            # Check if the attachment is a configuration
            if attachment.get("type") == "config":
                # Add the configuration to the viewer
                config_viewer.add_configuration(
                    attachment.get("content", {}),
                    name=attachment.get("metadata", {}).get("name", "Configuration")
                )