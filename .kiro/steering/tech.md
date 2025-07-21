# Technical Stack & Build System

## Tech Stack

### Core Technologies
- **Python 3.10+**: Primary programming language
- **Strands Agents SDK**: Framework for building AI agents
- **Model Context Protocol (MCP)**: Protocol for AI agent integration
- **AWS Shopfloor Connectivity (SFC)**: Industrial data connectivity framework

### Key Libraries & Dependencies
- **strands-agents**: Core agent framework
- **strands-agents-tools**: Tools for Strands agents
- **python-dotenv**: Environment variable management
- **fastmcp**: Fast MCP server implementation
- **mcp**: MCP client implementation
- **jmespath**: JSON query language for data extraction
- **markdown**: Markdown parsing and processing
- **black**: Code formatting

## Package Management

This project uses [uv](https://astral.sh/uv) for fast Python package management:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Build & Run Commands

### SFC Wizard Agent

```bash
# Initialize dependencies
cd agents/sfc_wizard_agent
./scripts/init.sh

# Run the agent
./scripts/run.sh
# OR
uv run python -m sfc_wizard.agent

# Run directly from GitHub
uvx --from git+https://github.com/aws-samples/sample-shopfloor-connectivity-agentic.git#subdirectory=agents/sfc_wizard_agent agent
```

### SFC Spec Server

```bash
# Initialize dependencies
cd mcp-servers/sfc-spec-server
./scripts/init.sh

# Run the server
./scripts/run.sh
# OR
uv run python -m sfc_spec.server

# Run directly from GitHub
uvx --from git+https://github.com/aws-samples/sample-shopfloor-connectivity-agentic.git#subdirectory=mcp-servers/sfc-spec-server sfc_spec
```

## Testing & Development

```bash
# Run tests
./scripts/test.sh

# Format code
./scripts/lint.sh
```

## Environment Configuration

Create a `.env` file in the agent directory with:

```env
# MCP Server Configuration (optional)
MCP_SERVER_COMMAND=uv
MCP_SERVER_ARGS=run,python
MCP_SERVER_PATH=../../../mcp-servers/sfc-spec-server/sfc_spec/server.py

# AWS Configuration (for deployment)
AWS_REGION=us-east-1
AWS_PROFILE=default
```

## MCP Integration

The SFC Wizard Agent integrates with the SFC Spec Server via MCP. Configuration example:

```json
{
  "mcpServers": {
    "sfc-spec-server": {
      "autoApprove": [],
      "disabled": false,
      "timeout": 5000,
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/aws-samples/sample-shopfloor-connectivity-agentic.git#subdirectory=mcp-servers/sfc-spec-server",
        "sfc_spec"
      ],
      "env": {}
    }
  }
}
```