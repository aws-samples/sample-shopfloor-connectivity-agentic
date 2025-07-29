"""
UI module for SFC Wizard Agent Chat Interface.
Implements the agent loop as a web-based chat conversation.
"""

import logging
import os
import secrets
import uuid
from datetime import datetime
from typing import Dict, List
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import threading

from .agent import SFCWizardAgent, stdio_mcp_client


class StreamingOutputCapture:
    """Capture and stream stdout/stderr output in real-time."""

    def __init__(
        self,
        socketio,
        session_id,
        original_stdout=None,
        original_stderr=None,
        stop_event=None,
    ):
        self.socketio = socketio
        self.session_id = session_id
        self.original_stdout = original_stdout or sys.stdout
        self.original_stderr = original_stderr or sys.stderr
        self.accumulated_output = ""
        self.last_emit_time = time.time()
        self.emit_interval = 0.1  # Emit every 100ms
        self.stop_event = stop_event

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
        if self.accumulated_output.strip() and (
            not self.stop_event or not self.stop_event.is_set()
        ):
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

        # Track active agent threads for stop functionality
        self.active_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}

        # SFC Wizard Agent will be initialized later within MCP context
        self.sfc_agent = None
        self.agent_ready = False

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
                with open(env_file_path, "r") as f:
                    content = f.read()

                # Look for existing FLASK_SECRET_KEY in .env file
                for line in content.split("\n"):
                    if line.strip().startswith("FLASK_SECRET_KEY="):
                        return line.split("=", 1)[1].strip()

                # If FLASK_SECRET_KEY not found in .env, generate and append it
                new_secret_key = secrets.token_urlsafe(32)
                with open(env_file_path, "a") as f:
                    f.write(
                        f"\n# Flask Secret Key (auto-generated)\nFLASK_SECRET_KEY={new_secret_key}\n"
                    )

                print(f"✅ Generated new Flask secret key and saved to .env file")
                return new_secret_key

            except Exception as e:
                print(f"⚠️ Error reading/writing .env file: {e}")

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

            # Create stop event for this session
            stop_event = threading.Event()
            self.stop_events[session_id] = stop_event

            # Process message with agent in background thread
            def process_agent_response(sid):
                streaming_capture = None
                try:
                    # Emit typing indicator
                    self.socketio.emit("agent_typing", {"typing": True}, room=sid)

                    # Signal start of streaming response with session context
                    self.socketio.emit(
                        "agent_streaming_start", {"session_id": session_id}, room=sid
                    )

                    # Create streaming output capture with stop event awareness
                    streaming_capture = StreamingOutputCapture(
                        self.socketio, sid, stop_event=stop_event
                    )

                    # Capture stdout and stderr for streaming
                    original_stdout = sys.stdout
                    original_stderr = sys.stderr

                    try:
                        # Redirect stdout and stderr to our streaming capture
                        sys.stdout = streaming_capture
                        sys.stderr = streaming_capture

                        # Check if generation was stopped before starting
                        if stop_event.is_set():
                            self.socketio.emit(
                                "generation_stopped",
                                {"message": "Generation was stopped before starting."},
                                room=sid,
                            )
                            return

                        # Process with SFC Agent with periodic stop checks
                        response = self._run_agent_with_stop_check(
                            user_message, stop_event, sid
                        )

                        # Check if generation was stopped during processing
                        if stop_event.is_set():
                            self.socketio.emit(
                                "generation_stopped",
                                {"message": "Generation was stopped by user."},
                                room=sid,
                            )
                            return

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

                    # Only proceed with response if not stopped
                    if not stop_event.is_set():
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

                    # Check if this was due to a stop event
                    if stop_event.is_set():
                        self.socketio.emit(
                            "generation_stopped",
                            {"message": "Generation was stopped by user."},
                            room=sid,
                        )
                    else:
                        error_msg = {
                            "role": "assistant",
                            "content": f"❌ Error processing request: {str(e)}\nPlease try rephrasing your question or check your configuration.",
                            "timestamp": datetime.now().isoformat(),
                        }
                        self.conversations[session_id].append(error_msg)
                        self.socketio.emit("agent_response", error_msg, room=sid)
                        self.logger.error(f"Error processing message: {str(e)}")
                finally:
                    # Clean up session tracking
                    if session_id in self.stop_events:
                        del self.stop_events[session_id]
                    if session_id in self.active_threads:
                        del self.active_threads[session_id]

                    # Stop typing indicator
                    self.socketio.emit("agent_typing", {"typing": False}, room=sid)

            # Run agent processing in background thread
            thread = threading.Thread(
                target=process_agent_response, args=(current_sid,)
            )
            thread.daemon = True
            self.active_threads[session_id] = thread
            thread.start()

        @self.socketio.on("stop_generation")
        def handle_stop_generation(data):
            """Handle request to stop generation."""
            session_id = session.get("session_id")
            if not session_id:
                return

            self.logger.info(f"Stop generation requested for session: {session_id}")

            # Set the stop event for this session
            if session_id in self.stop_events:
                self.stop_events[session_id].set()
                emit("generation_stop_acknowledged", {"session_id": session_id})
            else:
                emit(
                    "generation_stop_error",
                    {"message": "No active generation to stop."},
                )

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

    def _run_agent_with_stop_check(self, user_message, stop_event, session_id):
        """Run the agent with comprehensive output suppression when stopped."""
        import time
        import builtins

        class StoppableAgent:
            def __init__(self, agent, stop_event):
                self.agent = agent
                self.stop_event = stop_event
                self.result = None
                self.error = None
                self.completed = False

            def run_in_thread(self, message):
                """Run the agent in a separate thread with comprehensive output control."""
                try:
                    import sys
                    import os

                    # Store original functions
                    original_stdout_write = sys.stdout.write
                    original_stderr_write = sys.stderr.write
                    original_print = builtins.print
                    original_os_write = os.write

                    # Create suppressed versions
                    def suppressed_stdout_write(text):
                        if self.stop_event.is_set():
                            return len(text)  # Suppress output
                        return original_stdout_write(text)

                    def suppressed_stderr_write(text):
                        if self.stop_event.is_set():
                            return len(text)  # Suppress output
                        return original_stderr_write(text)

                    def suppressed_print(*args, **kwargs):
                        if self.stop_event.is_set():
                            return  # Suppress print
                        return original_print(*args, **kwargs)

                    def suppressed_os_write(fd, text):
                        if self.stop_event.is_set() and fd in (
                            1,
                            2,
                        ):  # stdout=1, stderr=2
                            return len(text) if isinstance(text, (bytes, str)) else 0
                        return original_os_write(fd, text)

                    # Apply patches
                    sys.stdout.write = suppressed_stdout_write
                    sys.stderr.write = suppressed_stderr_write
                    builtins.print = suppressed_print
                    os.write = suppressed_os_write

                    try:
                        # Run the agent
                        response = self.agent(message)

                        if not self.stop_event.is_set():
                            self.result = response
                        else:
                            self.result = "Generation stopped by user."
                    finally:
                        # Restore original functions
                        sys.stdout.write = original_stdout_write
                        sys.stderr.write = original_stderr_write
                        builtins.print = original_print
                        os.write = original_os_write

                except Exception as e:
                    if not self.stop_event.is_set():
                        self.error = str(e)
                    else:
                        self.result = "Generation stopped by user."
                finally:
                    self.completed = True

            def run_with_timeout(self, message, timeout=300):
                """Run the agent with timeout and stop check."""
                import threading

                # Start agent in background thread
                agent_thread = threading.Thread(
                    target=self.run_in_thread, args=(message,)
                )
                agent_thread.daemon = True
                agent_thread.start()

                # Wait for completion or stop event
                start_time = time.time()
                while agent_thread.is_alive() and not self.completed:
                    if self.stop_event.is_set():
                        # User requested stop - suppress output and wait briefly for graceful shutdown
                        print("🛑 Stop requested - suppressing agent output...")
                        time.sleep(1.0)  # Give more time for graceful shutdown
                        if agent_thread.is_alive():
                            print(
                                "⚠️ Agent thread still running in background (output suppressed)"
                            )
                            return "Generation stopped by user."
                        break

                    if time.time() - start_time > timeout:
                        return f"Generation timed out after {timeout} seconds."

                    time.sleep(0.1)  # Check every 100ms

                # Return result
                if self.error:
                    return f"Error: {self.error}"
                elif self.result:
                    if hasattr(self.result, "content"):
                        return str(self.result.content)
                    elif hasattr(self.result, "text"):
                        return str(self.result.text)
                    else:
                        return str(self.result)
                else:
                    return "No response generated."

        # Create and run the stoppable agent
        stoppable_agent = StoppableAgent(self.sfc_agent.agent, stop_event)
        return stoppable_agent.run_with_timeout(user_message)

    def _get_welcome_message(self) -> str:
        """Get the welcome message for new conversations."""
        return """🏭 **AWS SHOP FLOOR CONNECTIVITY (SFC) WIZARD**

Specialized assistant for industrial data connectivity to AWS

💾 **Session Persistence**: Your conversation is automatically saved and will persist for 5 minutes even if you refresh the page or close the browser tab.

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
            # Cleanup SFC processes
            print("🧹 Cleaning up SFC processes...")
            if self.sfc_agent:
                self.sfc_agent._cleanup_processes()


def main():
    """Main function to run the SFC Wizard Chat UI."""
    try:
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
