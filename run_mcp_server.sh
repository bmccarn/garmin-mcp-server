#!/bin/bash
# Run the Garmin Connect MCP Server
# Uses stdio transport by default — for HTTP, use Docker or fastmcp CLI
python "$(dirname "$0")/garmin_mcp_server.py"
