# Garmin Connect MCP Server

A Model Context Protocol (MCP) server that exposes your Garmin health and fitness data to AI models.

## Features

- **17 tools** for querying health data
- **MFA support** (SMS two-factor authentication)
- **Token persistence** - authenticate once, use for ~1 year
- **Date range queries** for trend analysis
- **Export to CSV/JSON**

## Quick Start

### 1. Setup Environment

```bash
# Using your existing conda environment
conda activate connect

# Or create a new one
conda create -n connect python=3.12
conda activate connect
pip install garminconnect fastmcp
```

### 2. Authenticate with Garmin

```bash
python garmin_auth.py
```

This will:
- Prompt for your Garmin email and password
- Send an SMS code if you have MFA enabled
- Save OAuth tokens to `~/.garminconnect/`

### 3. Run the MCP Server

```bash
# Direct run
python garmin_mcp_server.py

# Or with FastMCP CLI
fastmcp run garmin_mcp_server.py
```

## Available Tools

| Tool | Description |
|------|-------------|
| `get_todays_summary` | Comprehensive health summary for today |
| `get_daily_stats` | Steps, calories, distance, floors |
| `get_heart_rate` | HR data with time in zones |
| `get_sleep` | Sleep duration, stages, score |
| `get_stress` | Stress levels and duration |
| `get_body_battery` | Energy levels throughout day |
| `get_hrv` | Heart rate variability |
| `get_spo2` | Blood oxygen levels |
| `get_respiration` | Breathing rate data |
| `get_recent_activities` | Recent workouts/activities |
| `get_training_status` | VO2 max, training load |
| `get_training_readiness` | Recovery score |
| `get_body_composition` | Weight, BMI, body fat |
| `get_personal_records` | Personal bests |
| `get_devices` | Connected Garmin devices |
| `get_health_data_for_date_range` | Multi-day trend data |
| `get_weekly_summary` | 7-day summary with averages |

## LiteLLM Integration

### Option 1: Using LiteLLM's MCP Gateway (Recommended)

Add to your LiteLLM `config.yaml`:

```yaml
mcp_servers:
  garmin:
    command: "python"
    args: ["/path/to/garmin-connect-api/garmin_mcp_server.py"]
    transport: "stdio"
```

### Option 2: Using mcp_config.json

Create `mcp_config.json`:

```json
{
  "mcpServers": {
    "garmin": {
      "command": "/opt/homebrew/Caskroom/miniforge/base/envs/connect/bin/python",
      "args": ["/Users/blakemccarn/development/garmin-connect-api/garmin_mcp_server.py"]
    }
  }
}
```

### Option 3: HTTP Transport with FastMCP

Run the server with HTTP transport:

```bash
fastmcp run garmin_mcp_server.py --transport sse --port 8000
```

Then configure LiteLLM:

```yaml
mcp_servers:
  garmin:
    url: "http://localhost:8000"
    transport: "sse"
```

### Option 4: Claude Desktop Integration

Add to Claude Desktop's config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "garmin": {
      "command": "/opt/homebrew/Caskroom/miniforge/base/envs/connect/bin/python",
      "args": ["/Users/blakemccarn/development/garmin-connect-api/garmin_mcp_server.py"]
    }
  }
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GARMIN_EMAIL` | Garmin account email (optional, for auto-auth) |
| `GARMIN_PASSWORD` | Garmin account password (optional, for auto-auth) |

## Authentication Notes

- Tokens are stored in `~/.garminconnect/`
- Tokens are valid for approximately 1 year
- If tokens expire, run `python garmin_auth.py` again
- MFA codes are sent via SMS to your phone

## Files

| File | Description |
|------|-------------|
| `garmin_mcp_server.py` | MCP server with 17 health data tools |
| `garmin_auth.py` | Interactive authentication setup |
| `garmin_app.py` | Standalone CLI app with interactive menu |
| `run.sh` | Launch the CLI app |
| `run_mcp_server.sh` | Launch the MCP server |

## Example AI Queries

Once connected, you can ask your AI:

- "What's my health summary for today?"
- "How did I sleep last night?"
- "Show me my step count for the last 7 days"
- "What's my resting heart rate trend this week?"
- "List my recent activities"
- "What's my current body battery level?"
- "Compare my sleep this week vs last week"

## Troubleshooting

### Authentication Failed
```bash
# Re-run authentication
python garmin_auth.py
```

### MCP Server Won't Start
```bash
# Test imports
python -c "from garmin_mcp_server import mcp; print('OK')"

# Check for token file
ls ~/.garminconnect/
```

### Empty Data for Some Fields
Some fields (like stress) may be empty if:
- Your Garmin device doesn't track that metric
- Data hasn't synced yet
- The metric requires specific device features

## License

MIT
