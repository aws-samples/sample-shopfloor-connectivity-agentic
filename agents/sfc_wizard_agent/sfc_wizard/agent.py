#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) Wizard Agent
Specialized assistant for debugging, creating, and testing SFC configurations.
"""

import sys
import os
import json
import threading
import queue
import inspect
import html
from dotenv import load_dotenv

# Import the externalized functions
from sfc_wizard.tools.file_operations import SFCFileOperations
from sfc_wizard.tools.log_operations import SFCLogOperations
from sfc_wizard.tools.folder_operations import SFCFolderOperations
from sfc_wizard.tools.sfc_runner import SFCRunner
from sfc_wizard.tools.sfc_visualization import visualize_file_target_data
from sfc_wizard.tools.prompt_logger import PromptLogger
from sfc_wizard.tools.sfc_knowledge import load_sfc_knowledge

# Load environment variables
load_dotenv()

try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    from mcp import stdio_client, StdioServerParameters
    from strands.tools.mcp import MCPClient
except ImportError:
    print(
        "Strands SDK not found. Please run 'scripts/init.sh' to install dependencies."
    )
    sys.exit(1)


def _create_mcp_client():
    """Create MCP client from environment variables"""
    # Get MCP server configuration from environment variables - defaults to uvx based mcp runtime

    # NOTE: Use .env file at repo-root for local dev setup (copy 1:1 from .env.template as a start...)
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "uvx")
    mcp_args_str = os.getenv(
        "MCP_SERVER_ARGS",
        "--from,git+https://github.com/aws-samples/sample-shopfloor-connectivity-agentic.git#subdirectory=mcp-servers/sfc-spec-server",
    )
    mcp_path = os.getenv("MCP_SERVER_PATH", "sfc_spec")

    # Parse comma-separated args and add the path
    mcp_args = [arg.strip() for arg in mcp_args_str.split(",")]
    mcp_args.append(mcp_path)

    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=mcp_command,
                args=mcp_args,
            )
        )
    )


stdio_mcp_client = _create_mcp_client()


class color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


class SFCWizardAgent:
    """
    AWS Shopfloor Connectivity (SFC) Wizard Agent
    Specialized for debugging existing configurations, creating new ones,
    testing configurations, and defining environments.
    """

    def __init__(self):
        self.sfc_knowledge = load_sfc_knowledge()
        self.current_config = None
        self.validation_errors = []
        self.recommendations = []
        # Track active SFC processes for cleanup
        self.active_processes = []

        # Stop functionality
        self.stop_event = threading.Event()
        self.generation_lock = threading.Lock()
        self.is_generating = False

        # Initialize the prompt logger
        self.prompt_logger = PromptLogger(max_history=20, log_dir=".sfc")

        # Detect the running mode (UI or CLI)
        self.is_ui_mode = self._detect_ui_mode()

        # Initialize the Strands agent with SFC-specific tools
        self.agent = self._create_agent()

    def _detect_ui_mode(self) -> bool:
        """Detect if the agent is running in UI mode or CLI mode.

        Returns:
            bool: True if running in UI mode, False if running in CLI mode
        """
        # Check the call stack to determine if we're being called from the UI module
        for frame_info in inspect.stack():
            if "ui.py" in frame_info.filename or "sfc_wizard.ui" in frame_info.filename:
                return True
        return False

    def _create_agent(self) -> Agent:
        """Create a Strands agent with SFC-specific tools"""

        # Current running SFC config and log tail thread
        self.current_config_name = None
        self.log_tail_thread = None
        self.log_tail_stop_event = threading.Event()
        self.log_buffer = queue.Queue(maxsize=100)  # Buffer for log messages

        @tool
        def read_config_from_file(filename: str) -> str:
            """Read an SFC configuration from a JSON file.

            Args:
                filename: Name of the file to read the configuration from
            """
            return SFCFileOperations.read_config_from_file(filename)

        @tool
        def save_config_to_file(config_json: str, filename: str) -> str:
            """Save an SFC configuration to a JSON file.

            Args:
                config_json: SFC configuration to save
                filename: Name of the file to save the configuration to
            """
            return SFCFileOperations.save_config_to_file(config_json, filename)

        @tool
        def save_results_to_file(content: str, filename: str) -> str:
            """Save content to a file with specified extension (txt, vm, md).

            Args:
                content: Content to save to the file
                filename: Name of the file to save the content to (defaults to .txt extension if none provided)

            Notes:
                When an SFC configuration is running, this will save the file both to the
                central storage directory (.sfc/stored_results) and to the current run directory.
            """
            return SFCFileOperations.save_results_to_file(
                content, filename, self.current_config_name
            )

        @tool
        def run_sfc_config_locally(config_json: str, config_name: str = "") -> str:
            """Run an SFC configuration locally in a test environment.

            Downloads SFC resources and runs the configuration in a local test environment.

            Args:
                config_json: SFC configuration to run
                config_name: Optional name for the configuration and test folder (defaults to timestamp if not provided)
            """
            return self._run_sfc_config_locally(config_json, config_name)

        @tool
        def tail_logs(lines: int = 20, follow: bool = False) -> str:
            """Display the most recent lines from the SFC log file for the current running configuration.

            Args:
                lines: Number of recent log lines to show (default: 20)
                follow: If True, continuously display new log lines in real-time.
                        To exit follow mode, press Ctrl+C in the terminal.

            Note: When follow=True, the function will enter a real-time viewing mode.
                  The only way to exit this mode is by pressing Ctrl+C in the terminal.
                  After exiting, you'll be returned to the command prompt.

                  This feature is only available in CLI mode and will be disabled in UI mode.
            """
            # Disable follow mode in UI mode since it requires terminal interaction
            if self.is_ui_mode and follow:
                return "❌ Log follow mode is not available in the web interface. Please use the standard log viewing without the follow option."

            return SFCLogOperations.tail_logs(
                self.current_config_name, lines, follow, self.log_buffer
            )

        @tool
        def clean_runs_folder() -> str:
            """Clean the runs folder by removing all SFC runs to free up disk space.

            This tool will ask for confirmation (y/n) before deleting any files.
            Active configurations will be preserved.
            """
            return SFCFolderOperations.clean_runs_folder(
                current_config_name=self.current_config_name,
                last_config_name=self.last_config_name,
            )

        @tool
        def confirm_clean_runs_folder(confirmation: str) -> str:
            """Confirm and execute the cleaning of the runs folder after receiving user confirmation.

            Args:
                confirmation: User's response (y/n) to the deletion confirmation prompt
            """
            return SFCFolderOperations.confirm_clean_runs_folder(
                confirmation,
                current_config_name=self.current_config_name,
                last_config_name=self.last_config_name,
            )

        @tool
        def visualize_data(
            minutes: int = 10, jmespath_expr: str = "value", seconds: int = None
        ) -> str:
            """Visualize data from the currently running SFC configuration with FILE-TARGET enabled.

            Shows the data using a visualizer (ncurses in CLI mode or markdown in UI mode).

            Args:
                minutes: Number of minutes of data to visualize (default: 10, ignored if seconds is provided)
                jmespath_expr: JMESPath expression to extract values from the data (e.g., "sources.SinusSource.values.sinus.value")
                seconds: Optional number of seconds for finer time control (overrides minutes when provided)
                         For UI mode, you can specify smaller timeframes: 5, 10, 15, 20, 30, 50 seconds
            """
            # Debug print for UI mode detection
            print(f"🔍 Visualization UI mode detected: {self.is_ui_mode}")

            # Log timeframe info
            if seconds is not None:
                print(f"📊 Visualizing data from the last {seconds} seconds")
            else:
                print(f"📊 Visualizing data from the last {minutes} minutes")

            result = visualize_file_target_data(
                config_name=self.current_config_name,
                minutes=minutes,
                jmespath_expr=jmespath_expr,
                ui_mode=self.is_ui_mode,
                seconds=seconds,
            )

            # Force the visualization to print directly in UI mode
            if self.is_ui_mode:
                print(f"\n{result}\n")

            return result

        @tool
        def run_example(input_text: str) -> str:
            """Run the example SFC configuration when receiving 'example' as input.

            Args:
                input_text: The text input from the user
            """
            if input_text.lower().strip() == "example":
                # Path to the example config file
                example_config_path = "sfc-config-example.json"

                try:
                    # Read the example config file
                    with open(example_config_path, "r") as f:
                        config_json = f.read()

                    # Run the example configuration using the existing tool
                    return self._run_sfc_config_locally(config_json, "example-config")
                except Exception as e:
                    result = f"❌ Error running example configuration: {str(e)}"
                    return result
            else:
                result = f"Input '{input_text}' not recognized as 'example'. No action taken."
                return result

        @tool
        def save_conversation(count: int = 1) -> str:
            """Save the last N conversation exchanges as markdown files.

            Each file contains a user prompt and the agent's response, formatted in markdown.
            The filename is generated based on the content of the prompt.

            Args:
                count: Number of recent conversations to save (default: 1)
            """
            try:
                success, message = self.prompt_logger.save_n_conversations(count)
                if success:
                    return f"✅ {message}"
                else:
                    return f"❌ {message}"
            except Exception as e:
                return f"❌ Error saving conversations: {str(e)}"

        # Create agent with SFC-specific tools
        try:
            # Get model ID from environment variable with default value if not set
            model_id = os.getenv(
                "BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            )
            bedrock_model = BedrockModel(model_id=model_id)
            agent_internal_tools = [
                read_config_from_file,
                save_config_to_file,
                save_results_to_file,
                run_sfc_config_locally,
                tail_logs,
                clean_runs_folder,
                confirm_clean_runs_folder,
                visualize_data,
                run_example,
                save_conversation,
            ]

            mcp_tools = stdio_mcp_client.list_tools_sync()

            agent_system_prompt = """You are a specialized assistant for creating, validating & running SFC (stands for "Shop Floor Connectivity") configurations.
            "Use your MCP (shall be your main resource for validation) and internal tools to gather required information.
            "Always explain your reasoning and cite sources when possible."""

            agent = Agent(
                model=bedrock_model,
                tools=agent_internal_tools + mcp_tools,
                system_prompt=agent_system_prompt,
            )
        except Exception as e:
            print(e)
            agent = Agent(tools=agent_internal_tools)

        return agent

    def _run_sfc_config_locally(self, config_json: str, config_name: str = "") -> str:
        """Run SFC configuration locally in a test environment"""
        # Call the refactored method from SFCRunner
        (
            result,
            current_config_name,
            last_config_name,
            last_config_file,
            updated_processes,
            updated_log_tail_thread,
        ) = SFCRunner.run_sfc_config_locally(
            config_json=config_json,
            config_name=config_name,
            active_processes=self.active_processes,
            log_tail_thread=self.log_tail_thread,
            log_tail_stop_event=self.log_tail_stop_event,
            log_buffer=self.log_buffer,
        )

        # Update instance variables with results from refactored method
        self.current_config_name = current_config_name
        self.last_config_name = last_config_name
        self.last_config_file = last_config_file
        self.active_processes = updated_processes
        self.log_tail_thread = updated_log_tail_thread

        return result

    def boot(self):
        """Boot sequence for SFC Wizard"""
        print("=" * 43)
        print(
            color.BOLD
            + color.BLUE
            + "🏭 AWS SHOP FLOOR CONNECTIVITY (SFC) WIZARD"
            + color.END
        )
        print("=" * 43)
        print("Specialized assistant for industrial data connectivity to AWS")
        print()
        print("🎯 I can help you with:")
        print("• 🔍 Debug existing SFC configurations")
        print("• 🛠️  Create new SFC configurations")
        print("• 💾 Save configurations to JSON files")
        print("• 📄 Save results to text, markdown, or velocity template files")
        print("• 📂 Load configurations from JSON files")
        print("• ▶️  Run configurations in local test environments")
        print("• 🧪 Test configurations against environments")
        print("• 🏗️  Define required deployment environments")
        print("• 📚 Explain SFC concepts and components")
        print("• 📊 Visualize data from configurations with FILE-TARGET")
        print("• 📝 Save conversation exchanges as markdown files")
        print("• 🚀 Type 'example' to run a sample configuration instantly")
        print()
        print("📋 Supported Protocols:")
        protocol_list = list(self.sfc_knowledge["supported_protocols"].keys())
        for i in range(0, len(protocol_list), 4):
            print("   " + " | ".join(protocol_list[i : i + 4]))
        print()
        print("☁️ Supported AWS Targets:")
        aws_targets = list(self.sfc_knowledge["aws_targets"].keys())
        for i in range(0, len(aws_targets), 3):
            print("   " + " | ".join(aws_targets[i : i + 3]))
        print()
        print("💡 **How to use:**")
        print("• Type your questions and press Enter")
        print(
            "• Hold Control key + press S key (Ctrl+S) during response generation to stop it"
        )
        print("• Type 'exit' or 'quit' to end the session")
        print()

    def _cleanup_processes(self):
        """Clean up all running SFC processes when wizard exits"""
        if not self.active_processes:
            return

        print("\n🛑 Stopping all running SFC processes...")
        for process in self.active_processes:
            if process.poll() is None:  # Process is still running
                try:
                    process.terminate()
                    process.wait(timeout=2)  # Wait for up to 2 seconds
                except:
                    # If termination fails, force kill
                    try:
                        process.kill()
                    except:
                        pass
        print(f"✅ Terminated {len(self.active_processes)} SFC processes")
        self.active_processes = []

    def start_generation(self):
        """Mark the start of a new generation."""
        with self.generation_lock:
            self.stop_event.clear()
            self.is_generating = True

    def stop_generation(self):
        """Stop the current generation/processing and clean up."""
        with self.generation_lock:
            if self.is_generating:
                self.stop_event.set()
                self.is_generating = False

                # Stop any active log tail threads
                if (
                    hasattr(self, "log_tail_thread")
                    and self.log_tail_thread
                    and self.log_tail_thread.is_alive()
                ):
                    self.log_tail_stop_event.set()
                    try:
                        self.log_tail_thread.join(timeout=1)
                    except:
                        pass

                # Clean up any active processes
                self._cleanup_processes()

                return True
            else:
                return False

    def reset_for_new_request(self):
        """Reset agent state to be ready for new requests."""
        with self.generation_lock:
            self.is_generating = False
            self.stop_event.clear()

    def is_stopped(self):
        """Check if generation has been stopped."""
        return self.stop_event.is_set()

    def _process_with_stop_capability(self, user_input):
        """Process user input with ability to stop using Ctrl+S"""
        import signal

        response = None
        agent_thread = None

        def signal_handler(signum, frame):
            """Handle Ctrl+S signal to stop generation"""
            if self.is_generating:
                print(f"\n🛑 Generation stopped by user!")
                self.stop_generation()

        try:
            # Set up signal handler for Ctrl+S (SIGTSTP equivalent)
            original_handler = signal.signal(signal.SIGTSTP, signal_handler)

            print(f"\n🤖 Processing your request... (Ctrl+S to stop)")

            # Mark generation start
            self.start_generation()

            # Run agent in background thread
            def run_agent():
                nonlocal response
                try:
                    response = self.agent(user_input)
                except Exception as e:
                    response = f"❌ Error processing request: {str(e)}"

            agent_thread = threading.Thread(target=run_agent)
            agent_thread.daemon = True
            agent_thread.start()

            # Monitor for completion or stop
            while agent_thread.is_alive() and not self.is_stopped():
                agent_thread.join(timeout=0.1)

            if self.is_stopped():
                print("🛑 Generation stopped. You can continue with a new question.\n")
            else:
                # Record successful conversation
                if response and not isinstance(response, str):
                    self.prompt_logger.add_entry(user_input, response)
                print(f"\n")

        except KeyboardInterrupt:
            # Handle Ctrl+C
            print(f"\n🛑 Generation stopped by user!")
            self.stop_generation()
            print("You can continue with a new question.\n")
        except Exception as e:
            print(f"\n❌ Error processing request: {str(e)}")
            print("Please try rephrasing your question or check your configuration.\n")
        finally:
            # Restore original signal handler
            try:
                signal.signal(signal.SIGTSTP, original_handler)
            except:
                pass
            # Always reset generation state
            self.is_generating = False
            self.stop_event.clear()

    def run(self):
        """Main interaction loop"""
        self.boot()

        try:
            while True:
                try:
                    user_input = input(
                        color.BOLD + color.BLUE + "SFC Wizard: " + color.END
                    ).strip()

                    if user_input.lower() in ["exit", "quit", "bye"]:
                        print("\n🏭 Thank you for using the SFC Wizard!")
                        print("May your industrial data flow smoothly to the cloud! ☁️")
                        break

                    if not user_input:
                        continue

                    # Process with Strands agent in a threaded way to allow stop commands
                    self._process_with_stop_capability(user_input)

                except KeyboardInterrupt:
                    print("\n\n🏭 SFC Wizard session interrupted. Goodbye!")
                    break
                except Exception as e:
                    print(f"\n❌ Unexpected error: {str(e)}")
        finally:
            # Clean up all active SFC processes when wizard exits
            self._cleanup_processes()


def main():
    """Main function to run the SFC Wizard"""
    try:
        with stdio_mcp_client:
            wizard = SFCWizardAgent()
            wizard.run()
    except Exception as e:
        print(f"Error starting SFC Wizard: {str(e)}")
        print(
            "Please make sure all dependencies are installed by running 'scripts/init.sh'"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
