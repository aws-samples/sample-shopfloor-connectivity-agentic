"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Agent Interface Layer for the SFC Wizard Agent UI.

This module acts as a bridge between the Streamlit UI and the SFC Wizard Agent,
providing methods to send messages to the agent and process its responses.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import traceback

# Import the agent module
from sfc_wizard.agent import SFCWizardAgent

# Set up logging
logger = logging.getLogger(__name__)

class AgentInterface:
    """Interface between the Streamlit UI and the SFC Wizard Agent."""
    
    def __init__(self):
        """Initialize the agent interface."""
        self._agent = None
        self._initialized = False
        self._error = None
    
    def initialize(self) -> Tuple[bool, Optional[str]]:
        """
        Initialize the SFC Wizard Agent.
        
        Returns:
            Tuple[bool, Optional[str]]: A tuple containing a success flag and an error message if any.
        """
        try:
            # Initialize the agent
            self._agent = SFCWizardAgent()
            self._initialized = True
            return True, None
        except Exception as e:
            error_msg = f"Failed to initialize agent: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self._error = error_msg
            return False, error_msg
    
    @property
    def is_initialized(self) -> bool:
        """
        Check if the agent is initialized.
        
        Returns:
            bool: True if the agent is initialized, False otherwise.
        """
        return self._initialized
    
    @property
    def error(self) -> Optional[str]:
        """
        Get the last error message.
        
        Returns:
            Optional[str]: The last error message or None if no error occurred.
        """
        return self._error
    
    def send_message(self, message: str) -> Tuple[bool, Union[str, Dict[str, Any]], Optional[str]]:
        """
        Send a message to the agent and get its response.
        
        Args:
            message (str): The message to send to the agent.
            
        Returns:
            Tuple[bool, Union[str, Dict[str, Any]], Optional[str]]: 
                A tuple containing a success flag, the agent's response, and an error message if any.
        """
        if not self._initialized:
            return False, "", "Agent not initialized. Please initialize the agent first."
        
        try:
            # Send the message to the agent and get its response
            response = self._agent.process_message(message)
            return True, response, None
        except Exception as e:
            error_msg = f"Failed to process message: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self._error = error_msg
            return False, "", error_msg
    
    def process_response(self, response: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process the agent's response for display in the UI.
        
        Args:
            response (Union[str, Dict[str, Any]]): The agent's response.
            
        Returns:
            Dict[str, Any]: A processed response suitable for display in the UI.
        """
        processed_response = {
            "text": "",
            "attachments": []
        }
        
        try:
            # If the response is a string, just return it as text
            if isinstance(response, str):
                processed_response["text"] = response
                return processed_response
            
            # If the response is a dictionary, extract the text and any attachments
            if isinstance(response, dict):
                # Extract the main text response
                if "response" in response:
                    processed_response["text"] = response["response"]
                elif "text" in response:
                    processed_response["text"] = response["text"]
                elif "message" in response:
                    processed_response["text"] = response["message"]
                
                # Extract any configurations
                if "configuration" in response:
                    processed_response["attachments"].append({
                        "type": "config",
                        "content": response["configuration"],
                        "metadata": {"name": "Configuration"}
                    })
                
                # Extract any visualizations
                if "visualization" in response:
                    processed_response["attachments"].append({
                        "type": "visualization",
                        "content": response["visualization"],
                        "metadata": {"name": "Visualization"}
                    })
                
                # Extract any logs
                if "logs" in response:
                    processed_response["attachments"].append({
                        "type": "log",
                        "content": response["logs"],
                        "metadata": {"name": "Logs"}
                    })
            
            return processed_response
        except Exception as e:
            logger.error(f"Failed to process response: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "text": "Failed to process agent response. Please try again.",
                "attachments": []
            }
    
    def shutdown(self) -> None:
        """
        Shutdown the agent and clean up resources.
        """
        if self._initialized and self._agent:
            try:
                # Clean up any resources
                self._agent = None
                self._initialized = False
            except Exception as e:
                logger.error(f"Error during agent shutdown: {str(e)}")
                logger.error(traceback.format_exc())

# Create a singleton instance of the agent interface
agent_interface = AgentInterface()