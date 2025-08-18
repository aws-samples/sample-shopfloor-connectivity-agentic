# SFC Wizard Chat UI

A modern web-based chat interface for the SFC Wizard Agent that implements the Strands Agent Loop as an interactive conversation.

## Overview

The SFC Wizard Chat UI transforms the command-line SFC Wizard experience into a user-friendly web application. This implementation follows the [Strands Agent Loop](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/agent-loop/) pattern, providing a seamless chat-based interaction with the SFC Wizard Agent.

## Features

### 🎯 Core Functionality
- **Real-time Chat Interface**: WebSocket-based communication for instant responses
- **Agent Loop Integration**: Full implementation of the Strands agent loop in a chat context
- **Session Management**: Multiple users can have separate conversations
- **Conversation History**: Messages are preserved during the session
- **Typing Indicators**: Visual feedback when the agent is processing

### 🏭 SFC Wizard Capabilities
All original SFC Wizard features are available through the chat interface:
- 🔍 Debug existing SFC configurations
- 🛠️ Create new SFC configurations
- 💾 Save configurations to JSON files
- 📂 Load configurations from JSON files
- ▶️ Run configurations in local test environments
- 🧪 Test configurations against environments
- 🏗️ Define required deployment environments
- 📚 Explain SFC concepts and components
- 📊 Visualize data from configurations with FILE-TARGET
- 🚀 Quick example configuration with the 'example' command

### 🎨 User Experience
- **Modern Design**: Clean, professional interface with industrial theming
- **Responsive Layout**: Works on desktop, tablet, and mobile devices
- **Real-time Updates**: Live typing indicators and instant message delivery
- **Easy Navigation**: Clear conversation management and history
- **Accessibility**: Keyboard shortcuts and screen reader support

## Quick Start

### Method 1: Using the Run Script (Recommended)
```bash
cd agents/sfc_wizard_agent
./scripts/run-ui.sh
```

### Method 2: Direct Command
```bash
cd agents/sfc_wizard_agent
uv sync
uv run sfc-wizard-ui
```

### Method 3: Python Module
```bash
cd agents/sfc_wizard_agent
uv sync
uv run python -m sfc_wizard.ui
```

## Usage

1. **Start the UI**: Use one of the methods above to start the web server
2. **Open Browser**: Navigate to `http://127.0.0.1:5000` in your web browser
3. **Start Chatting**: Type your questions or commands in the chat interface
4. **Explore Features**: Try commands like:
   - `example` - Run a sample SFC configuration
   - `help` - Get help with SFC concepts
   - `create a modbus config` - Generate a new configuration
   - `explain OPCUA` - Learn about protocols

## Architecture

### Agent Loop Implementation

The UI implements the Strands Agent Loop as described in the documentation:

1. **User Input Processing**: Messages are received via WebSocket
2. **Agent Processing**: The SFC Wizard Agent processes the input using the Strands framework
3. **Tool Execution**: The agent can use all available SFC tools
4. **Response Generation**: Results are sent back to the user in real-time
5. **Conversation Continuity**: The full conversation context is maintained

### Technical Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Browser (Client)                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Chat Interface (HTML/JS)                   ││
│  │  • Message input/output                                 ││
│  │  • Real-time communication                              ││
│  │  • Typing indicators                                    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                │ WebSocket (Socket.IO)
                                │
┌─────────────────────────────────────────────────────────────┐
│                    Flask-SocketIO Server                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                   Chat UI Handler                       ││
│  │  • Session management                                   ││
│  │  • Message routing                                      ││
│  │  • Real-time communication                              ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
                                │ Direct Integration
                                │
┌─────────────────────────────────────────────────────────────┐
│                    SFC Wizard Agent                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 Strands Agent Loop                      ││
│  │  • LLM processing                                       ││
│  │  • Tool execution                                       ││
│  │  • Response generation                                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
sfc_wizard/
├── ui.py                    # Main UI application
│   ├── ChatUI class         # Flask-SocketIO application
│   ├── Route handlers       # HTTP endpoints
│   └── Socket handlers      # WebSocket events
├── templates/
│   └── chat.html           # Main chat interface
├── agent.py                # Original SFC Wizard Agent
└── tools/                  # SFC tool implementations
```

## Configuration

### Environment Variables

The UI uses the same environment variables as the original SFC Wizard, plus additional UI-specific configuration:

```bash
# Bedrock Model Configuration
BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0

# MCP Server Configuration
MCP_SERVER_COMMAND=uvx
MCP_SERVER_ARGS=--from,git+https://github.com/aws-samples/sample-shopfloor-connectivity-agentic.git#subdirectory=mcp-servers/sfc-spec-server
MCP_SERVER_PATH=sfc_spec

# Flask Secret Key (automatically generated during initialization)
FLASK_SECRET_KEY=your-secure-key-here
```

### Flask Secret Key

The web interface requires a secure secret key for session management. This key is automatically generated during the initialization process:

- **Automatic Generation**: When you run `./scripts/init.sh`, a cryptographically secure secret key is generated and added to your `.env` file
- **Session Security**: The secret key ensures that user sessions are secure and cannot be tampered with
- **Persistent Sessions**: With a proper secret key, user sessions will survive server restarts
- **Per-Installation Unique**: Each installation gets its own unique secret key for security

**Important Notes:**
- Never commit your `.env` file containing the secret key to version control
- If you lose your secret key, users will need to log in again (sessions will be invalidated) 
- For production deployments, ensure the secret key is properly secured and backed up

### UI-Specific Settings

The UI can be configured by modifying the `ChatUI` class initialization:

```python
# In ui.py
chat_ui = ChatUI(
    host='127.0.0.1',  # Change to '0.0.0.0' for external access
    port=5000           # Change port if needed
)
```

## Development

### Adding New Features

1. **New Tools**: Add tools to the `SFCWizardAgent` class - they will automatically be available in the chat
2. **UI Enhancements**: Modify the `chat.html` template for visual changes
3. **Backend Logic**: Extend the `ChatUI` class for new functionality

### Debugging

- Enable Flask debug mode by setting `debug=True` in the `run()` method
- Check browser console for client-side errors
- Monitor server logs for backend issues

## Deployment

### Local Network Access

To allow access from other devices on the local network:

```python
# In ui.py, change the host
chat_ui = ChatUI(host='0.0.0.0', port=5000)
```

### Production Considerations

For production deployment, consider:
- Using a production WSGI server (e.g., Gunicorn with eventlet)
- Adding SSL/TLS support
- Implementing authentication and authorization
- Setting up proper logging and monitoring
- Using a reverse proxy (nginx, Apache)

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   Error: [Errno 98] Address already in use
   ```
   Solution: Change the port in `ui.py` or kill the process using the port

2. **Dependencies Not Found**
   ```bash
   ImportError: No module named 'flask_socketio'
   ```
   Solution: Run `uv sync` to install dependencies

3. **Agent Errors**
   ```bash
   Error processing request: ...
   ```
   Solution: Check your AWS credentials and MCP server configuration

### Debug Mode

To enable detailed logging:

```python
# In ui.py
logging.basicConfig(level=logging.DEBUG)
chat_ui.run(debug=True)
```

## License

This project is licensed under the Apache-2.0 License - see the main repository LICENSE file for details.

## Contributing

Contributions are welcome! Please refer to the main repository's CONTRIBUTING.md for guidelines.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the main SFC Wizard documentation
3. Open an issue in the GitHub repository
