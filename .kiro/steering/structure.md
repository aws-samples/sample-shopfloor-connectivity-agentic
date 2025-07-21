# Project Structure & Organization

## Repository Layout

```
├── agents/                       # Agent implementations
│   └── sfc_wizard_agent/         # SFC Wizard Agent
│       ├── README.md             # Agent documentation
│       ├── pyproject.toml        # Project configuration and dependencies
│       ├── scripts/              # Utility scripts
│       │   ├── init.sh           # Initialize dependencies
│       │   ├── run.sh            # Run the agent
│       │   ├── test.sh           # Run tests
│       │   └── lint.sh           # Code linting
│       ├── sfc_wizard/           # Main agent package
│       │   ├── __init__.py
│       │   ├── agent.py          # Main agent implementation
│       │   └── tools/            # SFC-specific tools
│       │       ├── config_generator.py    # Configuration template generation
│       │       ├── config_validator.py    # Configuration validation
│       │       ├── data_visualizer.py     # Data visualization utilities
│       │       ├── diagnostics.py         # Issue diagnosis and optimization
│       │       ├── file_operations.py     # File I/O operations
│       │       ├── folder_operations.py   # Directory management
│       │       ├── log_operations.py      # Log monitoring and analysis
│       │       ├── sfc_explanations.py    # SFC concept explanations
│       │       ├── sfc_knowledge.py       # SFC knowledge base
│       │       ├── sfc_module_analyzer.py # SFC module analysis
│       │       ├── sfc_runner.py          # Local SFC execution
│       │       └── sfc_visualization.py   # Data visualization
│       └── sfc-config-example.json        # Example configuration file
│
├── mcp-servers/                  # MCP server implementations
│   └── sfc-spec-server/          # SFC Specification MCP Server
│       ├── README.md             # Server documentation
│       ├── pyproject.toml        # Project configuration and dependencies
│       ├── scripts/              # Utility scripts
│       │   ├── init.sh           # Initialize dependencies
│       │   ├── run.sh            # Run the server
│       │   ├── test.sh           # Run tests
│       │   └── lint.sh           # Code linting
│       └── sfc_spec/             # Main server package
│           ├── __init__.py
│           └── server.py         # MCP server implementation
│
├── src/                          # Source code for development
│   ├── agents/                   # Development version of agents
│   └── mcp-servers/              # Development version of MCP servers
│
├── .env                          # Environment variables (create from .env.template)
├── .env.template                 # Template for environment variables
├── .gitignore                    # Git ignore file
├── CODE_OF_CONDUCT.md            # Code of conduct
├── CONTRIBUTING.md               # Contribution guidelines
├── LICENSE                       # License information
└── README.md                     # Main project documentation
```

## Code Organization Patterns

### Agent Structure

The SFC Wizard Agent follows a modular design pattern:

1. **Main Agent Class (`agent.py`)**: 
   - Initializes the agent with tools and MCP client
   - Manages the agent lifecycle and interaction loop
   - Handles cleanup of resources

2. **Tool Modules (`tools/`)**: 
   - Each tool is implemented in a separate module
   - Tools are organized by functionality (config, diagnostics, file operations, etc.)
   - Tools are registered with the agent using the `@tool` decorator

3. **Knowledge Base (`sfc_knowledge.py`)**: 
   - Contains structured knowledge about SFC components, protocols, and targets
   - Used by various tools for validation, generation, and explanations

### MCP Server Structure

The SFC Spec Server follows the FastMCP pattern:

1. **Server Initialization**:
   - Creates a FastMCP server instance
   - Initializes the SFC repository if needed

2. **Tool Registration**:
   - Each tool is registered using the `@server.tool` decorator
   - Tools are organized by functionality (documentation, search, validation)

3. **Helper Functions**:
   - Common functionality is extracted into helper functions
   - Shared logic for file operations, document parsing, etc.

## Development Conventions

1. **Script Standardization**:
   - Both components use standardized script names (`init.sh`, `run.sh`, `test.sh`, `lint.sh`)
   - Scripts follow consistent patterns for initialization and execution

2. **Documentation**:
   - Comprehensive docstrings for all functions and classes
   - README files for each component with usage examples

3. **Error Handling**:
   - Structured error responses with status codes and messages
   - Graceful degradation when components or dependencies are unavailable

4. **Configuration Management**:
   - Environment variables for runtime configuration
   - Template files for configuration examples