#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

set -e  # Exit immediately if a command exits with a non-zero status

# Initialize the environment
echo "Setting up the MCP server environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install dependencies using uv
echo "Installing dependencies with uv..."
uv sync

echo "Setup complete!"
