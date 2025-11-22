#!/bin/bash
# Run the Garmin Connect MCP Server

# Initialize conda for the current shell
source /opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh

# Activate the connect environment
conda activate connect

# Run the MCP server
# Use stdio transport (default) for integration with MCP clients
python "$(dirname "$0")/garmin_mcp_server.py"
