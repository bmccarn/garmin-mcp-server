FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY garmin_mcp_server.py .
COPY garmin_auth.py .

# Token directory (mounted at runtime)
RUN mkdir -p /root/.garminconnect

# Expose the MCP server port
EXPOSE 8000

# Run the MCP server with Streamable HTTP transport (for native Open WebUI MCP support)
CMD ["fastmcp", "run", "garmin_mcp_server.py", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
