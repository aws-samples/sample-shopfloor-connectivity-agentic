#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) Wizard Agent
Specialized assistant for debugging, creating, and testing SFC configurations.
"""

import sys
import os
import threading
import queue
import inspect
import asyncio
import signal
import json
from pathlib import Path
from dotenv import load_dotenv

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Import the externalized functions
from sfc_wizard.tools.file_operations import SFCFileOperations
from sfc_wizard.tools.log_operations import SFCLogOperations
from sfc_wizard.tools.folder_operations import SFCFolderOperations
from sfc_wizard.tools.sfc_runner import SFCRunner
from sfc_wizard.tools.sfc_visualization import visualize_file_target_data
from sfc_wizard.tools.prompt_logger import PromptLogger
from sfc_wizard.tools.sfc_knowledge import load_sfc_knowledge

# Load environment variables from .env file (only once per process)
_env_loaded = False
if not _env_loaded:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✅ Loaded environment variables from {env_path}")
        _env_loaded = True
    else:
        # Try to load from repo root
        repo_env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if repo_env_path.exists():
            load_dotenv(dotenv_path=repo_env_path)
            print(f"✅ Loaded environment variables from {repo_env_path}")
            _env_loaded = True
        else:
            print("ℹ️ No .env file found, using default environment variables")
            _env_loaded = True

# Global AWS Bedrock configuration - configure once, use everywhere
AWS_BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)
AWS_BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")

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


def _get_test_payload_for_model(model_id: str) -> dict:
    """Get appropriate test payload based on model provider.

    Args:
        model_id: The Bedrock model ID

    Returns:
        Dictionary containing the test payload for the specific model type
    """
    model_lower = model_id.lower()

    if "anthropic" in model_lower or "claude" in model_lower:
        # Anthropic Claude models - use standard API version for all Claude models
        # The bedrock-2023-05-31 API version is more widely supported
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
        }
    elif "titan" in model_lower:
        # Amazon Titan Text models
        return {
            "inputText": "Hi",
            "textGenerationConfig": {
                "maxTokenCount": 1,
                "temperature": 0,
                "topP": 1,
                "stopSequences": [],
            },
        }
    elif "llama" in model_lower or "meta" in model_lower:
        # Meta Llama models
        return {"prompt": "Hi", "max_gen_len": 1, "temperature": 0.1, "top_p": 0.9}
    elif "ai21" in model_lower or "j2" in model_lower or "jamba" in model_lower:
        # AI21 Labs models
        return {"prompt": "Hi", "maxTokens": 1, "temperature": 0}
    elif "cohere" in model_lower:
        # Cohere Command models
        return {"prompt": "Hi", "max_tokens": 1, "temperature": 0}
    elif "mistral" in model_lower:
        # Mistral models
        return {"prompt": "Hi", "max_tokens": 1, "temperature": 0}
    else:
        # Generic fallback - use Anthropic format as it's most common
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
        }


def _validate_bedrock_service_access(
    session: boto3.Session, region: str, model_id: str
) -> tuple[bool, str]:
    """Validate access to Bedrock service and specific model.

    Args:
        session: Boto3 session
        region: AWS region
        model_id: Bedrock model ID

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        bedrock_client = session.client("bedrock", region_name=region)

        # Check if this is a cross-region model (starts with region prefix like "us.")
        is_cross_region = "." in model_id and model_id.split(".")[0] in [
            "us",
            "eu",
            "ap",
            "ca",
            "sa",
            "af",
            "me",
        ]

        # For cross-region models, strip the region prefix for availability check
        check_model_id = model_id
        if is_cross_region:
            # Remove the region prefix (e.g., "us." from "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
            check_model_id = ".".join(model_id.split(".")[1:])
            print(f"ℹ️  Detected cross-region model access: {model_id}")
            print(f"   Checking availability for base model: {check_model_id}")

        # Check general Bedrock access by listing foundation models
        try:
            # Try to list models for the provider of the configured model
            provider = "anthropic"  # Default to anthropic
            if "titan" in model_id.lower():
                provider = "amazon"
            elif "llama" in model_id.lower() or "meta" in model_id.lower():
                provider = "meta"
            elif "ai21" in model_id.lower() or "j2" in model_id.lower():
                provider = "ai21"
            elif "cohere" in model_id.lower():
                provider = "cohere"
            elif "mistral" in model_id.lower():
                provider = "mistral"

            models_response = bedrock_client.list_foundation_models(byProvider=provider)
            available_models = [
                model["modelId"] for model in models_response.get("modelSummaries", [])
            ]

            if check_model_id not in available_models:
                return (
                    False,
                    f"❌ AWS Credentials Error: Configured model '{model_id}' is not available in region {region}.\n"
                    f"   Available {provider.title()} models: {', '.join(available_models[:3])}{'...' if len(available_models) > 3 else ''}\n"
                    "   Please check:\n"
                    "   • Your BEDROCK_MODEL_ID environment variable (configured in .env file or system environment)\n"
                    "   • Model availability in your region\n"
                    "   • Your account has access to this specific model"
                    + (
                        f"\n   • Base model '{check_model_id}' should be available for cross-region access"
                        if is_cross_region
                        else ""
                    ),
                )

        except ClientError as list_error:
            # If we can't list models, we might still be able to invoke the specific model
            print(f"⚠️  Warning: Could not list foundation models: {list_error}")

        return (True, "")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ["UnauthorizedOperation", "AccessDenied"]:
            return (
                False,
                f"❌ AWS Credentials Error: Access denied to AWS Bedrock in region {region} "
                f"(BEDROCK_REGION={region} from .env file or system environment). Please ensure:\n"
                "   • Your AWS credentials have Bedrock permissions\n"
                "   • Bedrock is available in your region\n"
                "   • Your account has access to foundation models in Bedrock",
            )
        elif error_code == "InvalidUserID.NotFound":
            return (
                False,
                "❌ AWS Credentials Error: Invalid AWS credentials. Please check your access key and secret key.",
            )
        else:
            return (False, f"❌ AWS Credentials Error: {str(e)}")
    except Exception as e:
        if "Could not connect to the endpoint URL" in str(e):
            return (
                False,
                f"❌ AWS Credentials Error: Bedrock service not available in region {region} "
                f"(BEDROCK_REGION={region} from .env file or system environment). "
                "Please use a region where Bedrock is available (e.g., us-west-2, us-east-1).",
            )
        return (
            False,
            f"❌ AWS Credentials Error: Failed to connect to AWS Bedrock: {str(e)}",
        )


def _test_model_invocation(
    session: boto3.Session, region: str, model_id: str
) -> tuple[bool, str]:
    """Test actual model invocation to verify access.

    Args:
        session: Boto3 session
        region: AWS region
        model_id: Bedrock model ID

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        bedrock_runtime = session.client("bedrock-runtime", region_name=region)

        # Get model-specific test payload
        test_payload = _get_test_payload_for_model(model_id)

        # Make a minimal test call to verify model access
        bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(test_payload),
            contentType="application/json",
        )

        return (
            True,
            f"✅ AWS credentials and model access validated successfully for '{model_id}'.",
        )

    except ClientError as model_error:
        error_code = model_error.response["Error"]["Code"]
        error_message = model_error.response["Error"]["Message"]
        if error_code in ["AccessDeniedException", "UnauthorizedOperation"]:
            return (
                False,
                f"❌ AWS Model Access Error: No access to model '{model_id}' in region {region}.\n"
                "   Please ensure:\n"
                "   • Your AWS account has access to this specific model\n"
                "   • The model is enabled in your AWS Bedrock console\n"
                "   • Your IAM permissions include bedrock:InvokeModel for this model",
            )
        elif error_code == "ValidationException":
            return (
                False,
                f"❌ AWS Model Access Error: Invalid request for model '{model_id}'. "
                f"{error_message}. "
                "This may indicate the model payload format is incorrect or the model is not properly configured.",
            )
        elif error_code == "ResourceNotFoundException":
            return (
                False,
                f"❌ AWS Model Access Error: Model '{model_id}' not found in region {region}. "
                "Please check the model ID and ensure it's available in your region.",
            )
        else:
            return (
                False,
                f"❌ AWS Model Access Error: Failed to access model '{model_id}': {str(model_error)}",
            )
    except Exception as model_test_error:
        return (
            False,
            f"❌ AWS Model Access Error: Unable to test model '{model_id}' access: {str(model_test_error)}",
        )


def _validate_aws_credentials() -> tuple[bool, str]:
    """Validate AWS credentials for Bedrock access.

    Returns:
        tuple: (is_valid, error_message)
    """
    if not BOTO3_AVAILABLE:
        return (
            False,
            "❌ AWS Credentials Error: boto3 not available. Please install boto3 to use AWS Bedrock.",
        )

    try:
        # Check if we have any AWS credentials configured
        session = boto3.Session()
        credentials = session.get_credentials()

        if not credentials:
            return (
                False,
                "❌ AWS Credentials Error: No AWS credentials found. Please configure AWS credentials using one of:\n"
                "   • AWS CLI: aws configure\n"
                "   • Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY\n"
                "   • IAM roles (if running on EC2)\n"
                "   • AWS profiles in ~/.aws/credentials",
            )

        # Get region and model configuration
        region = AWS_BEDROCK_REGION
        model_id = AWS_BEDROCK_MODEL_ID

        # Validate Bedrock service access
        is_valid, error_msg = _validate_bedrock_service_access(
            session, region, model_id
        )
        if not is_valid:
            return (False, error_msg)

        # Test actual model invocation
        return _test_model_invocation(session, region, model_id)

    except ProfileNotFound as e:
        return (False, f"❌ AWS Credentials Error: AWS profile not found: {str(e)}")
    except NoCredentialsError:
        return (
            False,
            "❌ AWS Credentials Error: No AWS credentials found. Please configure AWS credentials.",
        )
    except Exception as e:
        return (
            False,
            f"❌ AWS Credentials Error: Unexpected error validating credentials: {str(e)}",
        )


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

        # Initialize the prompt logger
        self.prompt_logger = PromptLogger(max_history=20, log_dir=".sfc")

        # Detect the running mode (UI or CLI)
        self.is_ui_mode = self._detect_ui_mode()

        # Initialize streaming interrupt control for both CLI and UI mode
        self.streaming_interrupted = False
        self.streaming_task = None

        # UI mode interrupt state - will be set by UI when interruption is requested
        self.ui_interrupt_session = (
            None  # Store the session ID that requested interrupt
        )

        # Validate AWS credentials during initialization
        self.aws_credentials_valid, self.aws_credentials_error = (
            _validate_aws_credentials()
        )

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
            Example demo channel is: e.g. "sources.SimulatorSource.values.sinus.value" - simulationType sinus
            that is accesible for visualization from the file-target - approx. 20 sec after start, next to other channels.

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

        @tool
        def read_context_from_file(file_path: str) -> str:
            """Read content from various file types to use as context.

            Supports PDF, Excel (xls/xlsx), Markdown, CSV, Word (doc/docx), RTF, and TXT files.
            File size is limited to 500KB for performance reasons.

            Args:
                file_path: Path to the file (relative to where the agent was started)

            Returns:
                String containing the file content or error message
            """
            success, message, content = SFCFileOperations.read_context_from_file(
                file_path
            )
            if success and content:
                # Success case with content
                return f"{message}\n\n```\n{content}\n```"
            else:
                # Error case or no content
                return message

        # Create agent with SFC-specific tools
        try:
            # Use global Bedrock configuration
            bedrock_model = BedrockModel(
                model_id=AWS_BEDROCK_MODEL_ID, region_name=AWS_BEDROCK_REGION
            )
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
                read_context_from_file,
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

    def _signal_handler(self, signum, frame):
        """Handle SIGINT (Ctrl+C) during streaming response"""
        if not self.is_ui_mode and self.streaming_task:
            print(f"\n\n{color.YELLOW}⚡ Interrupting agent response...{color.END}")
            self.streaming_interrupted = True
            if self.streaming_task and not self.streaming_task.done():
                self.streaming_task.cancel()
            print(
                f"{color.GREEN}✅ Response interrupted. Ready for next query.{color.END}\n"
            )
        else:
            # Default interrupt behavior for non-streaming mode
            raise KeyboardInterrupt()

    async def _stream_response_async(self, user_input: str):
        """Stream agent response using Strands SDK proper streaming methods"""
        try:
            self.streaming_interrupted = False

            print(f"\n{color.CYAN}🤖 SFC Agent is thinking...{color.END}")
            print(
                f"{color.YELLOW}💡 Press Ctrl+C to interrupt the response at any time{color.END}\n"
            )

            # Try to use Strands SDK's built-in streaming response formatting
            try:
                # Check if there's a proper streaming response method
                if hasattr(self.agent, "stream"):
                    # Use the stream method if available
                    response_stream = self.agent.stream(user_input)
                    full_response = ""

                    if hasattr(response_stream, "__aiter__"):
                        # Async iterator
                        async for response_part in response_stream:
                            if self.streaming_interrupted:
                                break
                            # Print the formatted response part directly
                            print(str(response_part), end="", flush=True)
                            full_response += str(response_part)
                            await asyncio.sleep(0.001)
                    elif hasattr(response_stream, "__iter__"):
                        # Sync iterator - make it async
                        for response_part in response_stream:
                            if self.streaming_interrupted:
                                break
                            print(str(response_part), end="", flush=True)
                            full_response += str(response_part)
                            await asyncio.sleep(0.001)
                    else:
                        # Single response
                        full_response = str(response_stream)
                        print(full_response, end="", flush=True)

                else:
                    # Fallback to stream_async but try to get the formatted response
                    response_chunks = []
                    async for chunk in self.agent.stream_async(user_input):
                        if self.streaming_interrupted:
                            break
                        response_chunks.append(chunk)

                    # Try to extract the complete formatted response from the chunks
                    # Look for the final response in the last chunks
                    full_response = ""
                    for chunk in reversed(response_chunks[-5:]):  # Check last 5 chunks
                        if isinstance(chunk, str) and len(chunk) > len(full_response):
                            full_response = chunk
                            break
                        elif hasattr(chunk, "content") and hasattr(
                            chunk.content, "text"
                        ):
                            text = chunk.content.text
                            if len(text) > len(full_response):
                                full_response = text
                                break
                        elif isinstance(chunk, dict) and "response" in chunk:
                            text = str(chunk["response"])
                            if len(text) > len(full_response):
                                full_response = text
                                break

                    # Print the complete response
                    print(full_response, end="", flush=True)

                if not self.streaming_interrupted and full_response:
                    print(f"\n{color.GREEN}✅ Response complete{color.END}\n")
                    self.prompt_logger.add_entry(user_input, full_response)

            except Exception as streaming_error:
                print(
                    f"\n{color.YELLOW}⚠️  Streaming method failed, using regular response{color.END}"
                )
                # Complete fallback to regular agent call
                response = self.agent(user_input)
                response_text = str(response)
                print(f"\n{response_text}")
                self.prompt_logger.add_entry(user_input, response_text)

        except asyncio.CancelledError:
            print(f"\n{color.YELLOW}⚡ Stream cancelled{color.END}\n")
        except Exception as e:
            print(f"\n{color.RED}❌ Error during streaming: {str(e)}{color.END}")
            print("Falling back to regular response mode...")
            try:
                response = self.agent(user_input)
                response_text = str(response)
                print(f"\n{response_text}")
                self.prompt_logger.add_entry(user_input, response_text)
            except Exception as fallback_error:
                print(f"❌ Fallback error: {str(fallback_error)}")

    def _process_with_streaming_cli(self, user_input: str):
        """Process user input with streaming response in CLI mode"""
        if self.is_ui_mode:
            # UI mode - use regular processing
            response = self.agent(user_input)
            self.prompt_logger.add_entry(user_input, response)
            return

        # CLI mode - use streaming with interrupt capability
        loop = None
        try:
            # Create new event loop to avoid deprecation warning
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Set up signal handler for Ctrl+C
            original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)

            # Create streaming task
            self.streaming_task = loop.create_task(
                self._stream_response_async(user_input)
            )

            # Run the streaming task
            loop.run_until_complete(self.streaming_task)

        except KeyboardInterrupt:
            # Handle interrupt during setup/cleanup
            if self.streaming_task and not self.streaming_task.done():
                self.streaming_task.cancel()
                try:
                    # Wait for the task to be cancelled
                    loop.run_until_complete(self.streaming_task)
                except asyncio.CancelledError:
                    pass
            print(f"\n{color.YELLOW}⚡ Response interrupted{color.END}\n")
        except Exception as e:
            print(f"\n{color.RED}❌ Error in streaming mode: {str(e)}{color.END}")
            print("Falling back to regular response mode...")
            try:
                response = self.agent(user_input)
                self.prompt_logger.add_entry(user_input, response)
            except Exception as fallback_error:
                print(f"❌ Fallback error: {str(fallback_error)}")
        finally:
            # Clean up any remaining tasks before closing loop
            if loop and not loop.is_closed():
                # Cancel any pending tasks
                pending_tasks = [
                    task for task in asyncio.all_tasks(loop) if not task.done()
                ]
                if pending_tasks:
                    for task in pending_tasks:
                        task.cancel()
                    # Wait for all tasks to complete cancellation
                    try:
                        loop.run_until_complete(
                            asyncio.gather(*pending_tasks, return_exceptions=True)
                        )
                    except:
                        pass

                # Close the loop
                loop.close()

            # Restore original signal handler
            try:
                signal.signal(signal.SIGINT, original_sigint_handler)
            except:
                pass
            self.streaming_task = None

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

        # Display AWS credentials validation status
        if self.aws_credentials_valid:
            if not self.is_ui_mode:
                print(
                    f"{color.GREEN}✅ AWS Bedrock credentials validated successfully{color.END}"
                )
            else:
                print("✅ AWS Bedrock credentials validated successfully")
        else:
            if not self.is_ui_mode:
                print(f"{color.RED}{self.aws_credentials_error}{color.END}")
            else:
                print(self.aws_credentials_error)
        print()

        if not self.is_ui_mode:
            print(
                f"{color.YELLOW}⚡ NEW: Streaming responses with Ctrl+C interrupt capability!{color.END}"
            )
            print(
                f"   Press Ctrl+C during any response to interrupt and continue with next query"
            )
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
                        color.BOLD + color.BLUE + "\n\nSFC Wizard: " + color.END
                    ).strip()

                    if user_input.lower() in ["exit", "quit", "bye"]:
                        print("\n🏭 Thank you for using the SFC Wizard!")
                        print("May your industrial data flow smoothly to the cloud! ☁️")
                        break

                    if not user_input:
                        continue

                    # Process with Strands agent - use streaming in CLI mode
                    try:
                        self._process_with_streaming_cli(user_input)
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
