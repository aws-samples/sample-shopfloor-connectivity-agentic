#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) file operations module.
Handles reading and writing configuration files.
"""

import os
import json
from typing import Dict, Any, List


class SFCFileOperations:
    """Handles file operations for SFC configurations"""

    @staticmethod
    def read_config_from_file(filename: str) -> str:
        """Read configuration from a JSON file

        Args:
            filename: Name of the file to read the configuration from

        Returns:
            String result message with the loaded configuration
        """
        try:
            # Add file extension if not provided
            if not filename.lower().endswith(".json"):
                filename += ".json"

            # Check if file exists
            if not os.path.exists(filename):
                return f"❌ File not found: '{filename}'"

            # Read from file
            with open(filename, "r") as file:
                config = json.load(file)

            # Convert back to JSON string with proper indentation
            config_json = json.dumps(config, indent=2)

            return f"✅ Configuration loaded successfully from '{filename}':\n\n```json\n{config_json}\n```"
        except json.JSONDecodeError:
            return f"❌ Invalid JSON format in file: '{filename}'"
        except Exception as e:
            return f"❌ Error reading configuration: {str(e)}"

    @staticmethod
    def save_config_to_file(config_json: str, filename: str) -> str:
        """Save configuration to a JSON file

        Args:
            config_json: SFC configuration to save
            filename: Name of the file to save the configuration to

        Returns:
            String result message indicating success or failure
        """
        try:
            # Parse the JSON to ensure it's valid
            config = json.loads(config_json)

            # Add file extension if not provided
            if not filename.lower().endswith(".json"):
                filename += ".json"

            # Create the stored_configs directory if it doesn't exist
            storage_dir = ".sfc/stored_configs"
            os.makedirs(storage_dir, exist_ok=True)

            # Create the full path
            full_path = os.path.join(storage_dir, os.path.basename(filename))

            # Write to file
            with open(full_path, "w") as file:
                json.dump(config, file, indent=2)

            return f"✅ Configuration saved successfully to '{full_path}'"
        except json.JSONDecodeError:
            return "❌ Invalid JSON configuration provided"
        except Exception as e:
            return f"❌ Error saving configuration: {str(e)}"
            
    @staticmethod
    def save_results_to_file(content: str, filename: str, current_config_name: str = None) -> str:
        """Save content to a file with specified extension

        Args:
            content: Content to save to the file
            filename: Name of the file to save the content to
            current_config_name: Current config run name (optional)

        Returns:
            String result message indicating success or failure
        """
        try:
            # List of allowed file extensions
            allowed_extensions = ["txt", "vm", "md"]
            default_extension = "txt"
            
            # Check if filename has an extension
            has_extension = False
            for ext in allowed_extensions:
                if filename.lower().endswith(f".{ext}"):
                    has_extension = True
                    break
                    
            # Add default extension if no valid extension is provided
            if not has_extension:
                filename += f".{default_extension}"
            
            # Get base filename (without path)
            base_filename = os.path.basename(filename)
            
            # Create the stored_results directory if it doesn't exist
            storage_dir = ".sfc/stored_results"
            os.makedirs(storage_dir, exist_ok=True)
            
            # Create the full path for the main storage directory
            full_path = os.path.join(storage_dir, base_filename)
            
            # Write to file in the main storage directory
            with open(full_path, "w") as file:
                file.write(content)
            
            # Save additional copy in the current run directory if provided
            run_path = None
            if current_config_name:
                run_dir = os.path.join(".sfc/runs", current_config_name)
                if os.path.exists(run_dir):
                    run_path = os.path.join(run_dir, base_filename)
                    with open(run_path, "w") as file:
                        file.write(content)
            
            # Prepare the result message
            if run_path:
                return f"✅ Results saved successfully to:\n- '{full_path}'\n- '{run_path}'"
            else:
                return f"✅ Results saved successfully to '{full_path}'"
        except Exception as e:
            return f"❌ Error saving results: {str(e)}"
