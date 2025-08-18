"""
UI module for SFC Wizard Agent Chat Interface.
Implements the agent loop as a web-based chat conversation.
"""

import logging
import os
import secrets
import signal
import uuid
from datetime import datetime
from typing import Dict, List
import sys
import threading
import time
import asyncio
import platform
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import threading
import asyncio

from .agent import SFCWizardAgent, stdio_mcp_client


class StreamingOutputCapture:
    """Capture and stream stdout/stderr output in real-time."""

    def __init__(
        self, socketio, session_id, original_stdout=None, original_stderr=None
    ):
        self.socketio = socketio
        self.session_id = session_id
        self.original_stdout = original_stdout or sys.stdout
        self.original_stderr = original_stderr or sys.stderr
        self.accumulated_output = ""
        self.last_emit_time = time.time()
        self.emit_interval = 0.1  # Emit every 100ms

    def write(self, text):
        """Write method for capturing output."""
        if text.strip():  # Only process non-empty text
            self.accumulated_output += text
            current_time = time.time()

            # Emit accumulated output if enough time has passed or it's a significant chunk
            if (current_time - self.last_emit_time) >= self.emit_interval or len(
                self.accumulated_output
            ) > 100:
                self.emit_partial_response()
                self.last_emit_time = current_time

        # Also write to original stdout/stderr
        self.original_stdout.write(text)
        return len(text)

    def emit_partial_response(self):
        """Emit partial response to the client."""
        if self.accumulated_output.strip():
            self.socketio.emit(
                "agent_streaming",
                {
                    "content": self.accumulated_output,
                    "timestamp": datetime.now().isoformat(),
                },
                room=self.session_id,
            )
            self.accumulated_output = ""

    def flush(self):
        """Flush any remaining output."""
        if self.accumulated_output.strip():
            self.emit_partial_response()
        self.original_stdout.flush()


class ChatUI:
    """Web-based chat UI for SFC Wizard Agent."""

    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        # Get port from environment variable or use default
        self.port = int(os.getenv("FLASK_PORT", port))

        # Initialize Flask app
        self.app = Flask(__name__, template_folder="html", static_folder="html/assets")
        self.app.secret_key = self._get_or_generate_secret_key()

        # Initialize SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Store conversation history per session with timestamps
        self.conversations: Dict[str, List[Dict]] = {}
        self.session_timestamps: Dict[str, datetime] = {}
        self.session_expiry_minutes = 60

        # SFC Wizard Agent will be initialized later within MCP context
        self.sfc_agent = None
        self.agent_ready = False

        # Shared interrupt state for sessions
        self.session_interrupt_flags: Dict[str, bool] = {}
        self.session_streaming_tasks: Dict[str, asyncio.Task] = {}

        # Setup routes and socket handlers
        self._setup_routes()
        self._setup_socket_handlers()

        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def initialize_agent(self):
        """Initialize the SFC Wizard Agent within MCP context."""
        if self.sfc_agent is None:
            self.sfc_agent = SFCWizardAgent()
            self.agent_ready = True
            print("✅ SFC Wizard Agent initialized with MCP tools")

            # Display AWS credentials validation status in UI logs
            if self.sfc_agent.aws_credentials_valid:
                print("✅ AWS Bedrock credentials validated successfully")
            else:
                print(self.sfc_agent.aws_credentials_error)

    def _cleanup_async_tasks(self):
        """Clean up any pending asyncio tasks to prevent the 'Task was destroyed but it is pending' error."""
        try:
            # First, cancel all our tracked streaming tasks
            for session_id, task in list(self.session_streaming_tasks.items()):
                if not task.done():
                    task.cancel()
                    try:
                        # Give the task a moment to cancel gracefully
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(asyncio.wait_for(task, timeout=1.0))
                        loop.close()
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        # Task was cancelled or timed out, which is expected
                        pass
                    except Exception as e:
                        # Log any unexpected errors but continue cleanup
                        self.logger.warning(
                            f"Error cancelling task for session {session_id}: {e}"
                        )

            # Clear the task registry
            self.session_streaming_tasks.clear()
            self.session_interrupt_flags.clear()

            # Also clean up any other pending asyncio tasks that might be running
            try:
                # Try to get the current event loop if it exists
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None

                if current_loop:
                    # Cancel all pending tasks in the current loop
                    pending_tasks = [
                        task
                        for task in asyncio.all_tasks(current_loop)
                        if not task.done()
                    ]
                    if pending_tasks:
                        print(
                            f"🧹 Cancelling {len(pending_tasks)} pending asyncio tasks"
                        )
                        for task in pending_tasks:
                            task.cancel()

                        # Wait for all tasks to complete cancellation
                        try:
                            current_loop.run_until_complete(
                                asyncio.gather(*pending_tasks, return_exceptions=True)
                            )
                        except Exception as e:
                            # If we can't wait for them, at least we cancelled them
                            self.logger.warning(
                                f"Could not wait for task cancellation: {e}"
                            )

            except Exception as e:
                self.logger.warning(f"Could not clean up all asyncio tasks: {e}")

            print("✅ Cleaned up asyncio tasks")

        except Exception as e:
            self.logger.error(f"Error during async task cleanup: {e}")

    def _signal_handler(self, signum, frame):
        """Handle SIGINT (Ctrl+C) signal for clean shutdown."""
        print("\n🛑 Received interrupt signal, shutting down gracefully...")
        self._cleanup_async_tasks()
        if self.sfc_agent:
            self.sfc_agent._cleanup_processes()
        # Exit gracefully
        os._exit(0)

    def _get_or_generate_secret_key(self) -> str:
        """Get secret key from environment variable or generate a new one."""
        # First, try to get from environment variable
        secret_key = os.getenv("FLASK_SECRET_KEY")

        if secret_key:
            return secret_key

        # If not in environment, try to read from .env file
        env_file_path = os.path.join(os.path.dirname(__file__), "..", ".env")

        # Check if .env file exists
        if os.path.exists(env_file_path):
            try:
                # Use cross-platform file handling with pathlib
                env_path = Path(env_file_path)

                # Read content safely with universal newlines mode
                content = env_path.read_text(encoding="utf-8")

                # Look for existing FLASK_SECRET_KEY in .env file
                for line in content.splitlines():
                    if line.strip().startswith("FLASK_SECRET_KEY="):
                        return line.split("=", 1)[1].strip()

                # If FLASK_SECRET_KEY not found in .env, generate and append it
                new_secret_key = secrets.token_urlsafe(32)

                # Append to file with platform-appropriate line endings
                with open(env_file_path, "a", encoding="utf-8", newline="") as f:
                    f.write("\n# Flask Secret Key (auto-generated)\n")
                    f.write(f"FLASK_SECRET_KEY={new_secret_key}\n")

                print(f"✅ Generated new Flask secret key and saved to .env file")
                return new_secret_key

            except Exception as e:
                print(f"⚠️ Error reading/writing .env file: {e}")
                # Print more detailed error information for debugging
                import traceback

                traceback.print_exc()

        # If all else fails, generate a temporary secret key (not persistent)
        print(
            "⚠️ Using temporary secret key - sessions will not persist across restarts"
        )
        return secrets.token_urlsafe(32)

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route("/")
        def index():
            """Main chat interface."""
            # Check if session_id is provided as query parameter (from localStorage)
            client_session_id = request.args.get("session_id")
            if client_session_id:
                session["session_id"] = client_session_id
            elif "session_id" not in session:
                session["session_id"] = str(uuid.uuid4())
            return render_template("chat.html")

        @self.app.route("/health")
        def health():
            """Health check endpoint."""
            return jsonify({"status": "healthy", "service": "SFC Wizard Chat UI"})

        @self.app.route("/ready")
        def ready():
            """Agent readiness check endpoint."""
            if self.agent_ready and self.sfc_agent is not None:
                return jsonify({"status": "ready", "agent": "initialized"})
            else:
                return jsonify({"status": "not_ready", "agent": "initializing"}), 503

    def _setup_socket_handlers(self):
        """Setup SocketIO event handlers."""

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection."""
            # Check if agent is ready before allowing connections
            if not self.agent_ready or self.sfc_agent is None:
                emit(
                    "agent_not_ready",
                    {"message": "Agent is still initializing. Please wait..."},
                )
                return False

            self.logger.info("Client connected - waiting for session registration")

        @self.socketio.on("register_session")
        def handle_register_session(data):
            """Handle session registration from client with localStorage session ID."""
            client_session_id = data.get("sessionId")

            if client_session_id and client_session_id.startswith("session_"):
                # Use the client's session ID
                session["session_id"] = client_session_id
                session_id = client_session_id
                self.logger.info(f"Registered client session: {session_id}")
            else:
                # Generate new session ID if invalid
                session_id = str(uuid.uuid4())
                session["session_id"] = session_id
                self.logger.info(f"Generated new session: {session_id}")

            # Record session timestamp
            self.session_timestamps[session_id] = datetime.now()

            # Initialize conversation for session if it doesn't exist
            if session_id not in self.conversations:
                self.conversations[session_id] = []
                # Send welcome message
                welcome_message = self._get_welcome_message()
                formatted_welcome = welcome_message
                self.conversations[session_id].append(
                    {
                        "role": "assistant",
                        "content": formatted_welcome,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                self.logger.info(f"Created new conversation for session: {session_id}")
            else:
                self.logger.info(
                    f"Restored existing conversation for session: {session_id} ({len(self.conversations[session_id])} messages)"
                )

            # Send conversation history to client - with safety check
            try:
                conversation_messages = self.conversations.get(session_id, [])
                emit("conversation_history", {"messages": conversation_messages})
            except Exception as e:
                self.logger.error(f"Error sending conversation history: {str(e)}")
                # Initialize empty conversation and try again
                self.conversations[session_id] = []
                welcome_message = self._get_welcome_message()
                formatted_welcome = welcome_message
                self.conversations[session_id].append(
                    {
                        "role": "assistant",
                        "content": formatted_welcome,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                emit(
                    "conversation_history", {"messages": self.conversations[session_id]}
                )

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection."""
            session_id = session.get("session_id")
            self.logger.info(f"Client disconnected: {session_id}")

        @self.socketio.on("interrupt_response")
        def handle_interrupt_response():
            """Handle interruption request for streaming response."""
            session_id = session.get("session_id")
            self.logger.info(f"Response interruption requested by client: {session_id}")

            # Set the interrupt flag for this session
            if session_id:
                self.session_interrupt_flags[session_id] = True

                # If there's an active streaming task, cancel it
                if session_id in self.session_streaming_tasks:
                    task = self.session_streaming_tasks[session_id]
                    if not task.done():
                        task.cancel()

                # Set the interrupt flag on the agent if it exists
                if self.sfc_agent and hasattr(self.sfc_agent, "streaming_interrupted"):
                    self.sfc_agent.streaming_interrupted = True

                # Emit confirmation that interruption was processed
                emit("agent_streaming_end", {}, room=request.sid)

                return {"status": "success", "message": "Response interrupted"}
            else:
                return {"status": "error", "message": "No valid session"}

        @self.socketio.on("send_message")
        def handle_message(data):
            """Handle incoming chat message."""
            # Double-check agent readiness
            if not self.agent_ready or self.sfc_agent is None:
                emit(
                    "agent_response",
                    {
                        "role": "assistant",
                        "content": "❌ Agent is not ready yet. Please refresh the page and try again.",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                return

            # Ensure we have a valid session_id
            session_id = session.get("session_id")
            if not session_id:
                session_id = str(uuid.uuid4())
                session["session_id"] = session_id

            user_message = data.get("message", "").strip()

            if not user_message:
                return

            # Add user message to conversation
            user_msg = {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat(),
            }

            # Initialize conversation if it doesn't exist
            if session_id not in self.conversations:
                self.conversations[session_id] = []

            self.conversations[session_id].append(user_msg)

            # Echo user message back to client
            emit("message_received", user_msg)

            # Check for exit commands
            if user_message.lower() in ["exit", "quit", "bye"]:
                goodbye_content = "🏭 Thank you for using the SFC Wizard!\nMay your industrial data flow smoothly to the cloud! ☁️"
                formatted_goodbye = goodbye_content
                goodbye_msg = {
                    "role": "assistant",
                    "content": formatted_goodbye,
                    "timestamp": datetime.now().isoformat(),
                }
                self.conversations[session_id].append(goodbye_msg)
                emit("agent_response", goodbye_msg)
                return

            # Capture session ID and socket ID before spawning thread
            current_sid = request.sid

            # Process message with agent in background thread
            def process_agent_response(sid):
                streaming_capture = None
                try:
                    # Emit typing indicator
                    self.socketio.emit("agent_typing", {"typing": True}, room=sid)

                    # Signal start of streaming response
                    self.socketio.emit("agent_streaming_start", {}, room=sid)

                    # Create streaming output capture
                    streaming_capture = StreamingOutputCapture(self.socketio, sid)

                    # Capture stdout and stderr for streaming
                    original_stdout = sys.stdout
                    original_stderr = sys.stderr

                    try:
                        # Redirect stdout and stderr to our streaming capture
                        sys.stdout = streaming_capture
                        sys.stderr = streaming_capture

                        # Initialize interrupt state for this session
                        self.session_interrupt_flags[session_id] = False

                        # Use true streaming instead of blocking call
                        response = None
                        full_response = ""

                        # Use the same streaming approach as CLI
                        try:
                            # Create event loop for async streaming
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                            async def stream_response():
                                nonlocal full_response
                                try:
                                    # First try using the agent.stream method like CLI does
                                    if hasattr(self.sfc_agent.agent, "stream"):
                                        response_stream = self.sfc_agent.agent.stream(
                                            user_message
                                        )

                                        if hasattr(response_stream, "__aiter__"):
                                            # Async iterator
                                            async for response_part in response_stream:
                                                if self.session_interrupt_flags.get(
                                                    session_id, False
                                                ):
                                                    print(
                                                        "\n⚡ Response interrupted by user request."
                                                    )
                                                    break

                                                # Use the same approach as CLI - convert to string and emit
                                                chunk_text = str(response_part)
                                                full_response += chunk_text

                                                # Emit chunk directly to client
                                                self.socketio.emit(
                                                    "agent_streaming",
                                                    {
                                                        "content": chunk_text,
                                                        "timestamp": datetime.now().isoformat(),
                                                    },
                                                    room=sid,
                                                )

                                                await asyncio.sleep(
                                                    0.001
                                                )  # Match CLI timing
                                        elif hasattr(response_stream, "__iter__"):
                                            # Sync iterator - make it async like CLI does
                                            for response_part in response_stream:
                                                if self.session_interrupt_flags.get(
                                                    session_id, False
                                                ):
                                                    print(
                                                        "\n⚡ Response interrupted by user request."
                                                    )
                                                    break

                                                chunk_text = str(response_part)
                                                full_response += chunk_text

                                                self.socketio.emit(
                                                    "agent_streaming",
                                                    {
                                                        "content": chunk_text,
                                                        "timestamp": datetime.now().isoformat(),
                                                    },
                                                    room=sid,
                                                )

                                                await asyncio.sleep(0.001)
                                        else:
                                            # Single response
                                            full_response = str(response_stream)
                                            self.socketio.emit(
                                                "agent_streaming",
                                                {
                                                    "content": full_response,
                                                    "timestamp": datetime.now().isoformat(),
                                                },
                                                room=sid,
                                            )

                                    elif hasattr(self.sfc_agent.agent, "stream_async"):
                                        # Fallback to stream_async like CLI does
                                        response_chunks = []
                                        async for (
                                            chunk
                                        ) in self.sfc_agent.agent.stream_async(
                                            user_message
                                        ):
                                            if self.session_interrupt_flags.get(
                                                session_id, False
                                            ):
                                                print(
                                                    "\n⚡ Response interrupted by user request."
                                                )
                                                break
                                            response_chunks.append(chunk)

                                        # Extract the complete formatted response from chunks like CLI does
                                        for chunk in reversed(
                                            response_chunks[-5:]
                                        ):  # Check last 5 chunks
                                            if isinstance(chunk, str) and len(
                                                chunk
                                            ) > len(full_response):
                                                full_response = chunk
                                                break
                                            elif hasattr(chunk, "content") and hasattr(
                                                chunk.content, "text"
                                            ):
                                                text = chunk.content.text
                                                if len(text) > len(full_response):
                                                    full_response = text
                                                    break
                                            elif (
                                                isinstance(chunk, dict)
                                                and "response" in chunk
                                            ):
                                                text = str(chunk["response"])
                                                if len(text) > len(full_response):
                                                    full_response = text
                                                    break

                                        # Emit the complete response
                                        if full_response:
                                            self.socketio.emit(
                                                "agent_streaming",
                                                {
                                                    "content": full_response,
                                                    "timestamp": datetime.now().isoformat(),
                                                },
                                                room=sid,
                                            )

                                    else:
                                        # No streaming available
                                        raise Exception("No streaming method available")

                                except asyncio.CancelledError:
                                    print("\n⚡ Streaming cancelled")
                                    raise
                                except Exception as e:
                                    print(f"Error in streaming: {e}")
                                    raise

                            # Create and store the streaming task
                            streaming_task = loop.create_task(stream_response())
                            self.session_streaming_tasks[session_id] = streaming_task

                            try:
                                loop.run_until_complete(streaming_task)
                                response = type(
                                    "MockResponse", (), {"content": full_response}
                                )()
                            except asyncio.CancelledError:
                                response = type(
                                    "MockResponse",
                                    (),
                                    {
                                        "content": full_response
                                        + "\n[Response interrupted]"
                                    },
                                )()
                            except Exception as streaming_error:
                                # Fallback to regular agent call like CLI does
                                print(
                                    f"⚠️ Streaming method failed, using regular response: {streaming_error}"
                                )
                                response = self.sfc_agent.agent(user_message)
                            finally:
                                loop.close()
                                if session_id in self.session_streaming_tasks:
                                    del self.session_streaming_tasks[session_id]
                        except Exception as e:
                            # Final fallback to regular agent call
                            print(f"Error in streaming setup: {e}")
                            response = self.sfc_agent.agent(user_message)

                        # Ensure any remaining output is flushed
                        streaming_capture.flush()

                        # For visualization data, force flush any pending output
                        if "visualize" in user_message.lower():
                            print(
                                "Ensuring visualization data is properly displayed..."
                            )
                            self.socketio.sleep(
                                0.5
                            )  # Short delay to ensure output is processed

                    finally:
                        # Always restore original stdout/stderr
                        sys.stdout = original_stdout
                        sys.stderr = original_stderr

                    # Format the response for UI display - ensure it's a string
                    if hasattr(response, "content"):
                        formatted_response = str(response.content)
                    elif hasattr(response, "text"):
                        formatted_response = str(response.text)
                    else:
                        formatted_response = str(response)

                    # Signal end of streaming
                    self.socketio.emit("agent_streaming_end", {}, room=sid)

                    # Create response message - just add to conversation history,
                    # but don't send again to client to avoid duplication
                    agent_msg = {
                        "role": "assistant",
                        "content": formatted_response,
                        "timestamp": datetime.now().isoformat(),
                    }

                    # Add to conversation history
                    self.conversations[session_id].append(agent_msg)

                    # No need to emit agent_response here as streaming already showed the content

                except Exception as e:
                    # Ensure streaming is ended even on error
                    if streaming_capture:
                        streaming_capture.flush()
                    self.socketio.emit("agent_streaming_end", {}, room=sid)

                    error_msg = {
                        "role": "assistant",
                        "content": f"❌ Error processing request: {str(e)}\nPlease try rephrasing your question or check your configuration.",
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.conversations[session_id].append(error_msg)
                    self.socketio.emit("agent_response", error_msg, room=sid)
                    self.logger.error(f"Error processing message: {str(e)}")
                finally:
                    # Stop typing indicator
                    self.socketio.emit("agent_typing", {"typing": False}, room=sid)

            # Run agent processing in background thread
            thread = threading.Thread(
                target=process_agent_response, args=(current_sid,)
            )
            thread.daemon = True
            thread.start()

        @self.socketio.on("clear_conversation")
        def handle_clear_conversation(data=None):
            """Handle request to clear conversation."""
            # Get the session ID - check if a new one was provided in data
            if data and data.get("sessionId"):
                # Use the new session ID provided by the client
                new_session_id = data.get("sessionId")
                session["session_id"] = new_session_id
                session_id = new_session_id
                self.logger.info(f"Session reset with new ID: {session_id}")
            else:
                # Use existing session ID
                session_id = session.get("session_id")
                if not session_id:
                    session_id = str(uuid.uuid4())
                    session["session_id"] = session_id

            # Initialize conversation for the session ID
            self.conversations[session_id] = []

            # Clear agent's conversation context/memory by reinitializing it
            if self.sfc_agent is not None:
                try:
                    # Reinitialize the agent to clear its conversation context
                    self.sfc_agent = SFCWizardAgent()
                    self.logger.info(f"Agent context cleared for session: {session_id}")
                except Exception as e:
                    self.logger.error(f"Error clearing agent context: {str(e)}")

            # Send new welcome message
            welcome_message = self._get_welcome_message()
            formatted_welcome = welcome_message
            self.conversations[session_id].append(
                {
                    "role": "assistant",
                    "content": formatted_welcome,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            emit("conversation_cleared", {"messages": self.conversations[session_id]})

            # Update session timestamp in server-side records
            self.session_timestamps[session_id] = datetime.now()

    def _get_welcome_message(self) -> str:
        """Get the welcome message for new conversations."""
        # Get AWS credentials status from agent if available
        aws_status_message = ""
        if hasattr(self, "sfc_agent") and self.sfc_agent:
            if self.sfc_agent.aws_credentials_valid:
                aws_status_message = (
                    "✅ **AWS Bedrock credentials validated successfully**\n\n"
                )
            else:
                aws_status_message = f"❌ **AWS Credentials Issue:**\n{self.sfc_agent.aws_credentials_error}\n\n"

        return f"""🏭 **AWS SHOP FLOOR CONNECTIVITY (SFC) WIZARD**

Specialized assistant for industrial data connectivity to AWS

{aws_status_message}💾 **Session Persistence**: Your conversation is automatically saved and will persist for 5 minutes even if you refresh the page or close the browser tab.

⚡ **NEW: Streaming responses with interrupt capability!** Use the Stop button during any response to interrupt and continue with next query.

🎯 **I can help you with:**
• 🔍 Debug existing SFC configurations
• 🛠️ Create new SFC configurations  
• 💾 Save configurations to JSON files
• 📂 Load configurations from JSON files
• ▶️ Run configurations in local test environments
• 🧪 Test configurations against environments
• 🏗️ Define required deployment environments
• 📚 Explain SFC concepts and components
• 📊 Visualize data from configurations with FILE-TARGET
• 🚀 Type 'example' to run a sample configuration instantly

📋 **Supported Protocols:**
OPCUA | MODBUS | S7 | MQTT | HTTP | and more...

☁️ **Supported AWS Targets:**
AWS-S3 | AWS-IOT-CORE | AWS-TIMESTREAM | DEBUG | and more...

What would you like to do today?"""

    def run(self, debug=False):
        """Run the Flask-SocketIO server."""
        print("=" * 60)
        print("🏭 SFC WIZARD CHAT UI STARTING")
        print("=" * 60)
        print(f"🌐 Chat interface available at: http://{self.host}:{self.port}")
        print("📱 Open the URL in your web browser to start chatting")
        print("🔄 Real-time chat with the SFC Wizard Agent")
        print("=" * 60)

        # Set up signal handler for graceful shutdown - with Windows compatibility
        try:
            # Set up common signals available on all platforms
            signal.signal(signal.SIGINT, self._signal_handler)

            # Set up SIGTERM which might not be available on Windows
            if hasattr(signal, "SIGTERM"):  # Check if SIGTERM exists
                signal.signal(signal.SIGTERM, self._signal_handler)

            # On Windows, also try to handle CTRL_C_EVENT and CTRL_BREAK_EVENT if available
            if platform.system() == "Windows":
                if hasattr(signal, "CTRL_C_EVENT"):
                    signal.signal(signal.CTRL_C_EVENT, self._signal_handler)
                if hasattr(signal, "CTRL_BREAK_EVENT"):
                    signal.signal(signal.CTRL_BREAK_EVENT, self._signal_handler)
        except Exception as e:
            print(f"⚠️ Warning: Could not set up some signal handlers: {e}")
            print("   Graceful shutdown on keyboard interrupt may not work properly.")

        try:
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=debug,
                allow_unsafe_werkzeug=True,
            )
        except KeyboardInterrupt:
            print("\n🛑 SFC Wizard Chat UI stopped by user")
        except Exception as e:
            print(f"❌ Error starting chat UI: {str(e)}")
        finally:
            # Cleanup SFC processes and asyncio tasks
            print("🧹 Cleaning up SFC processes and async tasks...")
            self._cleanup_async_tasks()
            if self.sfc_agent:
                self.sfc_agent._cleanup_processes()


def main():
    """Main function to run the SFC Wizard Chat UI."""
    try:
        # Set appropriate event loop policy for Windows
        if platform.system() == "Windows":
            try:
                # Set the event loop policy to properly handle async on Windows
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                print("✅ Set Windows-compatible event loop policy")
            except Exception as e:
                print(f"⚠️ Could not set Windows event loop policy: {e}")

        # Load environment variables from .env file
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print(f"✅ Loaded environment variables from {env_path}")
        else:
            # Try to load from repo root
            repo_env_path = Path(__file__).parent.parent.parent.parent / ".env"
            if repo_env_path.exists():
                load_dotenv(dotenv_path=repo_env_path)
                print(f"✅ Loaded environment variables from {repo_env_path}")
            else:
                print("ℹ️ No .env file found, using default environment variables")

        with stdio_mcp_client:
            chat_ui = ChatUI(host="127.0.0.1")
            # Initialize agent within MCP context
            chat_ui.initialize_agent()
            chat_ui.run(debug=False)
    except Exception as e:
        print(f"Error starting SFC Wizard Chat UI: {str(e)}")
        print(
            "Please make sure all dependencies are installed by running 'scripts/init.sh'"
        )


if __name__ == "__main__":
    main()
