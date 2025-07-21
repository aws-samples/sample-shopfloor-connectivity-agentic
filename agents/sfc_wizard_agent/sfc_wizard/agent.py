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
from dotenv import load_dotenv

# Import UI module
try:
    from sfc_wizard.ui import launch_app

    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False

# Import the externalized functions
from sfc_wizard.tools.config_generator import generate_config_template
from sfc_wizard.tools.sfc_knowledge import load_sfc_knowledge
from sfc_wizard.tools.config_validator import SFCConfigValidator
from sfc_wizard.tools.diagnostics import diagnose_issue, suggest_optimizations
from sfc_wizard.tools.sfc_explanations import explain_concept
from sfc_wizard.tools.file_operations import SFCFileOperations
from sfc_wizard.tools.log_operations import SFCLogOperations
from sfc_wizard.tools.folder_operations import SFCFolderOperations
from sfc_wizard.tools.sfc_runner import SFCRunner
from sfc_wizard.tools.sfc_visualization import visualize_file_target_data

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

        # Initialize the Strands agent with SFC-specific tools

        self.agent = self._create_agent()

    # _load_sfc_knowledge method has been externalized to src/tools/sfc_knowledge.py

    def _create_agent(self) -> Agent:
        """Create a Strands agent with SFC-specific tools"""

        # Current running SFC config and log tail thread
        self.current_config_name = None
        self.log_tail_thread = None
        self.log_tail_stop_event = threading.Event()
        self.log_buffer = queue.Queue(maxsize=100)  # Buffer for log messages

        @tool
        def validate_sfc_config(config_json: str) -> str:
            """Validate an SFC configuration file for correctness and completeness.

            Args:
                config_json: JSON string containing the SFC configuration
            """
            try:
                # Parse the configuration
                config = json.loads(config_json)
                self.current_config = config

                # Create validator instance and validate the config
                validator = SFCConfigValidator(self.sfc_knowledge)
                is_valid = validator.validate_config(config)

                # Store validation results
                self.validation_errors = validator.get_errors()
                self.recommendations = validator.get_recommendations()

                # Return validation results
                if not is_valid:
                    return f"❌ Configuration validation failed:\n" + "\n".join(
                        self.validation_errors
                    )
                else:
                    result = "✅ Configuration is valid!"
                    if self.recommendations:
                        result += "\n\n💡 Recommendations:\n" + "\n".join(
                            self.recommendations
                        )
                    return result

            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON format: {str(e)}"
            except Exception as e:
                return f"❌ Validation error: {str(e)}"

        @tool
        def create_sfc_config_template(
            protocol: str, target: str, environment: str = "development"
        ) -> str:
            """Create an SFC configuration template for a specific protocol and target.

            Args:
                protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
                target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
                environment: Environment type (development, production)
            """
            return generate_config_template(
                protocol.upper(), target.upper(), environment, self.sfc_knowledge
            )

        @tool
        def diagnose_sfc_issue(issue_description: str, config_json: str = "") -> str:
            """Diagnose common SFC issues and provide troubleshooting steps.

            Args:
                issue_description: Description of the problem
                config_json: Optional SFC configuration (if available)
            """
            return diagnose_issue(issue_description, config_json, self.sfc_knowledge)

        @tool
        def suggest_sfc_optimization(
            config_json: str, performance_requirements: str = ""
        ) -> str:
            """Suggest optimizations for an SFC configuration based on performance requirements.

            Args:
                config_json: Current SFC configuration
                performance_requirements: Description of performance needs
            """
            return suggest_optimizations(
                config_json, performance_requirements, self.sfc_knowledge
            )

        @tool
        def generate_environment_specs(
            protocol: str, devices: str, data_volume: str, targets: str
        ) -> str:
            """Generate environment specifications needed for SFC deployment.

            Args:
                protocol: Primary protocol to be used
                devices: Description of devices to connect
                data_volume: Expected data volume and frequency
                targets: Target AWS services or systems
            """
            return generate_environment_specs(
                protocol, devices, data_volume, targets, self.sfc_knowledge
            )

        @tool
        def explain_sfc_concept(concept: str) -> str:
            """Explain SFC concepts, components, or configuration options.

            Args:
                concept: SFC concept to explain (e.g., schedules, transformations, filters)
            """
            return explain_concept(concept, self.sfc_knowledge)

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
        def run_sfc_config_locally(config_json: str, config_name: str = "") -> str:
            """Run an SFC configuration locally in a test environment.

            Downloads SFC resources and runs the configuration in a local test environment.

            Args:
                config_json: SFC configuration to run
                config_name: Optional name for the configuration and test folder (defaults to timestamp if not provided)
            """
            return self._run_sfc_config_locally(config_json, config_name)

        @tool
        def what_is_sfc() -> str:
            """Provides an explanation of what Shop Floor Connectivity (SFC) is and its key features."""
            return what_is_sfc()

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
            """
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
        def visualize_data(minutes: int = 10, jmespath_expr: str = "value") -> str:
            """Visualize data from the currently running SFC configuration with FILE-TARGET enabled.

            Shows the data from the last N minutes using an ncurses-based visualizer.

            Args:
                minutes: Number of minutes of data to visualize (default: 10)
                jmespath_expr: JMESPath expression to extract values from the data (e.g., "sources.SinusSource.values.sinus.value")
            """
            return visualize_file_target_data(
                config_name=self.current_config_name,
                minutes=minutes,
                jmespath_expr=jmespath_expr,
            )

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
                    return f"❌ Error running example configuration: {str(e)}"
            else:
                return f"Input '{input_text}' not recognized as 'example'. No action taken."

        # Create agent with SFC-specific tools
        try:
            # Get model ID from environment variable with default value if not set
            model_id = os.getenv(
                "BEDROCK_MODEL_ID", "eu.anthropic.claude-3-7-sonnet-20250219-v1:0"
            )
            bedrock_model = BedrockModel(model_id=model_id)
            agent_internal_tools = [
                validate_sfc_config,
                create_sfc_config_template,
                # diagnose_sfc_issue,
                # suggest_sfc_optimization,
                # generate_environment_specs,
                # explain_sfc_concept,
                read_config_from_file,
                save_config_to_file,
                run_sfc_config_locally,
                # what_is_sfc,
                tail_logs,
                clean_runs_folder,
                confirm_clean_runs_folder,
                visualize_data,
                run_example,
            ]
            mcp_tools = stdio_mcp_client.list_tools_sync()
            # print(mcp_tools)
            agent = Agent(model=bedrock_model, tools=agent_internal_tools + mcp_tools)
        except Exception as e:
            print(e)
            agent = Agent(tools=agent_internal_tools)

        return agent

    # Validation methods have been externalized to src/tools/config_validator.py

    # _generate_config_template method has been externalized to src/tools/config_generator.py

    # _diagnose_issue method has been externalized to src/tools/diagnostics.py

    # _suggest_optimizations method has been externalized to src/tools/diagnostics.py

    # _generate_environment_specs method has been externalized to src/tools/sfc_explanations.py

    # _what_is_sfc method has been externalized to src/tools/sfc_explanations.py

    # _explain_concept method has been externalized to src/tools/sfc_explanations.py

    # _read_config_from_file method has been externalized to src/tools/file_operations.py

    # _run_sfc_config_locally method has been externalized to src/tools/sfc_runner.py

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

    # _analyze_sfc_config_for_modules method has been externalized to src/tools/sfc_module_analyzer.py

    # _save_config_to_file method has been externalized to src/tools/file_operations.py

    # _log_tail_worker method has been externalized to src/tools/log_operations.py

    # _clean_runs_folder method has been externalized to src/tools/folder_operations.py

    # _confirm_clean_runs_folder method has been externalized to src/tools/folder_operations.py

    # _tail_logs method has been externalized to src/tools/log_operations.py

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
        print("• 📂 Load configurations from JSON files")
        print("• ▶️  Run configurations in local test environments")
        print("• 🧪 Test configurations against environments")
        print("• 🏗️  Define required deployment environments")
        print("• 📚 Explain SFC concepts and components")
        print("• 📊 Visualize data from configurations with FILE-TARGET")
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

        # Launch the web UI if available
        if UI_AVAILABLE:
            try:
                ui_url = launch_app(open_browser=True)
                print(f"🌐 Web UI available at: {ui_url}")
            except Exception as e:
                print(f"⚠️ Failed to launch Web UI: {str(e)}")
                print("   You can still use the command-line interface.")

        print("Type 'exit' or 'quit' to end the session.")
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

                    # Process with Strands agent
                    try:
                        response = self.agent(user_input)
                        print(f"\n")
                        # Don't print response here as stdio_mcp_client already prints it
                        # print(f"\n{response}\n")
                    except Exception as e:
                        print(f"\n❌ Error processing request: {str(e)}")
                        print(
                            "Please try rephrasing your question or check your configuration.\n"
                        )

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
