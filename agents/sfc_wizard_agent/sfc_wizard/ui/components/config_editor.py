"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Configuration Editor Component for the SFC Wizard Agent UI.

This module provides components for editing SFC configurations with validation feedback
and save functionality.
"""

import streamlit as st
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import jsonschema
from jsonschema import validators, ValidationError

from sfc_wizard.ui.utils.formatting import format_json
from sfc_wizard.ui.utils.session import conversation_state, error_handler
from sfc_wizard.ui.components.config_viewer import config_viewer


# SFC Configuration Schema (simplified version for validation)
SFC_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["sources", "targets"],
    "properties": {
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "protocol"],
                "properties": {
                    "name": {"type": "string"},
                    "protocol": {"type": "string"},
                }
            }
        },
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                }
            }
        }
    }
}


class ConfigurationEditor:
    """Class for editing and validating SFC configurations."""
    
    def __init__(self):
        """Initialize the configuration editor."""
        # Initialize session state for edited configurations if it doesn't exist
        if "edited_configurations" not in st.session_state:
            st.session_state.edited_configurations = {}
    
    def validate_configuration(self, config: Union[Dict[str, Any], str]) -> Tuple[bool, List[str]]:
        """
        Validate a configuration against the SFC schema.
        
        Args:
            config (Union[Dict[str, Any], str]): The configuration to validate.
            
        Returns:
            Tuple[bool, List[str]]: A tuple containing a validation success flag and a list of error messages.
        """
        # Parse the configuration if it's a string
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as e:
                return False, [f"Invalid JSON: {str(e)}"]
        
        # Validate against the schema
        errors = []
        try:
            jsonschema.validate(instance=config, schema=SFC_CONFIG_SCHEMA)
            return True, []
        except ValidationError as e:
            # Extract the error message and path
            path = ".".join(str(p) for p in e.path) if e.path else "root"
            errors.append(f"Error at {path}: {e.message}")
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors
    
    def render_editor(self, config_id: str = None, initial_config: Union[Dict[str, Any], str] = None, name: str = None) -> None:
        """
        Render a configuration editor in the UI.
        
        Args:
            config_id (str, optional): The ID of an existing configuration to edit. Defaults to None.
            initial_config (Union[Dict[str, Any], str], optional): Initial configuration data for a new editor. Defaults to None.
            name (str, optional): The name of the configuration. Defaults to None.
        """
        # Generate a unique key for this editor instance
        editor_key = f"editor_{uuid.uuid4()}"
        
        # Get the configuration to edit
        config_to_edit = None
        config_name = name or "New Configuration"
        
        if config_id:
            # Get the configuration from the viewer
            config_data = config_viewer.get_configuration(config_id)
            if config_data:
                config_to_edit = config_data["config"]
                config_name = config_data["name"]
        elif initial_config is not None:
            config_to_edit = initial_config
        
        # If no configuration is provided, start with an empty template
        if config_to_edit is None:
            config_to_edit = {
                "sources": [
                    {
                        "name": "example_source",
                        "protocol": "OPC-UA",
                        "server": {
                            "endpoint": "opc.tcp://localhost:4840"
                        }
                    }
                ],
                "targets": [
                    {
                        "name": "example_target",
                        "type": "DEBUG",
                        "active": True
                    }
                ]
            }
        
        # Convert the configuration to a formatted JSON string
        if isinstance(config_to_edit, (dict, list)):
            config_str = format_json(config_to_edit)
        else:
            config_str = str(config_to_edit)
        
        # Store the initial configuration in session state if it's not already there
        if editor_key not in st.session_state.edited_configurations:
            st.session_state.edited_configurations[editor_key] = {
                "config_id": config_id,
                "config_str": config_str,
                "config_name": config_name,
                "is_valid": True,
                "validation_errors": []
            }
        
        # Create a text area for editing the configuration
        st.text_area(
            "Edit Configuration JSON",
            value=st.session_state.edited_configurations[editor_key]["config_str"],
            height=400,
            key=f"{editor_key}_textarea",
            on_change=self._handle_config_change,
            args=(editor_key,)
        )
        
        # Display validation status
        is_valid = st.session_state.edited_configurations[editor_key]["is_valid"]
        validation_errors = st.session_state.edited_configurations[editor_key]["validation_errors"]
        
        if is_valid:
            st.success("Configuration is valid")
        else:
            st.error("Configuration has validation errors:")
            for error in validation_errors:
                st.error(error)
        
        # Add buttons for saving and resetting
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Save Configuration", key=f"{editor_key}_save", disabled=not is_valid):
                self._save_configuration(editor_key)
        
        with col2:
            if st.button("Reset", key=f"{editor_key}_reset"):
                self._reset_configuration(editor_key)
    
    def _handle_config_change(self, editor_key: str) -> None:
        """
        Handle changes to the configuration in the editor.
        
        Args:
            editor_key (str): The key of the editor instance.
        """
        # Get the updated configuration string
        config_str = st.session_state[f"{editor_key}_textarea"]
        
        # Update the stored configuration
        st.session_state.edited_configurations[editor_key]["config_str"] = config_str
        
        # Validate the configuration
        try:
            # Try to parse the JSON
            config = json.loads(config_str)
            
            # Validate against the schema
            is_valid, validation_errors = self.validate_configuration(config)
            
            # Update the validation status
            st.session_state.edited_configurations[editor_key]["is_valid"] = is_valid
            st.session_state.edited_configurations[editor_key]["validation_errors"] = validation_errors
        
        except json.JSONDecodeError as e:
            # If parsing fails, mark as invalid
            st.session_state.edited_configurations[editor_key]["is_valid"] = False
            st.session_state.edited_configurations[editor_key]["validation_errors"] = [f"Invalid JSON: {str(e)}"]
    
    def _save_configuration(self, editor_key: str) -> None:
        """
        Save the edited configuration.
        
        Args:
            editor_key (str): The key of the editor instance.
        """
        # Get the edited configuration
        config_str = st.session_state.edited_configurations[editor_key]["config_str"]
        config_id = st.session_state.edited_configurations[editor_key]["config_id"]
        config_name = st.session_state.edited_configurations[editor_key]["config_name"]
        
        try:
            # Parse the JSON
            config = json.loads(config_str)
            
            # Add the configuration to the viewer
            new_config_id = config_viewer.add_configuration(config, name=config_name)
            
            # Update the editor state
            st.session_state.edited_configurations[editor_key]["config_id"] = new_config_id
            
            # Show a success message
            st.success(f"Configuration '{config_name}' saved successfully!")
            
            # Rerun to update the UI
            st.rerun()
        
        except json.JSONDecodeError as e:
            st.error(f"Failed to save configuration: Invalid JSON: {str(e)}")
        except Exception as e:
            st.error(f"Failed to save configuration: {str(e)}")
    
    def _reset_configuration(self, editor_key: str) -> None:
        """
        Reset the configuration to its initial state.
        
        Args:
            editor_key (str): The key of the editor instance.
        """
        # Remove the editor state to reset it
        if editor_key in st.session_state.edited_configurations:
            del st.session_state.edited_configurations[editor_key]
        
        # Rerun to update the UI
        st.rerun()


# Create a singleton instance of the configuration editor
config_editor = ConfigurationEditor()


def render_config_editor(config_id: str = None, initial_config: Union[Dict[str, Any], str] = None, name: str = None) -> None:
    """
    Render the configuration editor interface.
    
    Args:
        config_id (str, optional): The ID of an existing configuration to edit. Defaults to None.
        initial_config (Union[Dict[str, Any], str], optional): Initial configuration data for a new editor. Defaults to None.
        name (str, optional): The name of the configuration. Defaults to None.
    """
    st.header("⚙️ Configuration Editor")
    
    # Allow the user to name the configuration
    if name:
        config_name = st.text_input("Configuration Name", value=name)
    else:
        config_name = st.text_input("Configuration Name", value="New Configuration")
    
    # Render the editor
    config_editor.render_editor(config_id, initial_config, config_name)