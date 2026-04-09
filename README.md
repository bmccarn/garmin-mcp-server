# Garmin Connect MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes your Garmin Connect health and fitness data to AI assistants. Ask your AI about your sleep, heart rate, workouts, stress, body battery, and more.

## Features

- **34 tools** covering health metrics, activities, trends, and comparisons
- **Streamable HTTP transport** — works with any MCP-compatible client
- **Docker-ready** — one command to build and run
- **Token persistence** — authenticate once with Garmin, tokens last ~1 year
- **MFA support** — handles SMS two-factor authentication
- **Parallel data fetching** — weekly reports pull 7+ days of data concurrently
- **Imperial units** — distances converted to miles automatically

## Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Authenticate with Garmin (one-time)
pip install garminconnect
python garmin_auth.py

# 2. Build and run
docker compose up -d

# Server is now at http://localhost:8000/mcp
```

### Option 2: Run Directly

```bash
# Install dependencies
pip install -r requirements.txt

# Authenticate (if you haven't already)
python garmin_auth.py

# Run the server
python garmin_mcp_server.py
# Or with FastMCP CLI:
fastmcp run garmin_mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8000
```

## Authentication

Garmin Connect uses OAuth tokens stored in `~/.garminconnect/`. Run the auth script once:

```bash
python garmin_auth.py
```

This will:
1. Prompt for your Garmin email and password
2. Handle MFA if enabled (SMS code)
3. Save OAuth tokens to `~/.garminconnect/`

Tokens last approximately one year. If they expire, just run `garmin_auth.py` again.

You can also set environment variables for non-interactive auth:
```bash
export GARMIN_EMAIL="your@email.com"
export GARMIN_PASSWORD="your-password"
```

## Available Tools (34)

### Daily Health
| Tool | Description |
|------|-------------|
| `get_todays_summary` | Comprehensive health summary (steps, HR, sleep, stress, body battery) |
| `get_daily_stats` | Steps, calories, distance, floors for a date |
| `get_heart_rate` | Heart rate data with resting HR and time in zones |
| `get_sleep` | Sleep duration, stages, score, avg HR, awake count |
| `get_stress` | Stress levels and time at each level |
| `get_body_battery` | Energy levels throughout the day |
| `get_body_battery_events` | What caused energy changes (activities, stress, rest) |
| `get_hrv` | Heart rate variability |
| `get_spo2` | Blood oxygen levels |
| `get_respiration` | Breathing rate data |
| `get_hydration` | Water intake data |
| `get_floors_data` | Detailed floors climbed data |
| `get_all_day_stress` | Stress data with timestamps throughout the day |
| `get_daily_goals_progress` | Progress toward daily goals |

### Activities & Training
| Tool | Description |
|------|-------------|
| `get_recent_activities` | Recent workouts/activities |
| `get_last_activity` | Most recent activity with all key metrics |
| `get_activity_details` | Detailed info including splits and laps |
| `get_activity_exercise_sets` | Sets, reps, and weight for strength training |
| `get_activities_by_type` | Filter by type (running, cycling, strength_training, etc.) |
| `search_activities` | Search by name, date range, distance, duration |
| `get_training_status` | VO2 max, training load, fitness metrics |
| `get_training_readiness` | Recovery score and readiness info |
| `get_personal_records` | Personal bests across activities |
| `get_badges` | Earned achievements |
| `get_step_streak` | Step goal streak info |

### Body & Composition
| Tool | Description |
|------|-------------|
| `get_body_composition` | Weight, BMI, body fat percentage |
| `get_weight_history` | Weight trends over time (up to 365 days) |

### Trends & Reports
| Tool | Description |
|------|-------------|
| `get_weekly_summary` | 7-day summary with averages |
| `get_weekly_health_report` | Comprehensive 7-day report (sleep, HRV, stress, body battery, training, weight — all in one call) |
| `get_health_data_for_date_range` | Multi-day data for selected metrics |
| `get_sleep_quality_trends` | Sleep quality over multiple days |
| `get_recovery_metrics` | HRV + sleep + stress + body battery recovery view |
| `compare_periods` | Compare two time periods side by side |

### Device
| Tool | Description |
|------|-------------|
| `get_devices` | Connected Garmin devices |

## Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "garmin": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Any MCP Client (Streamable HTTP)

Point your client at:
```
http://localhost:8000/mcp
```

The server uses Streamable HTTP transport, which is supported by the MCP SDK and most modern clients.

### LiteLLM

Add to your LiteLLM `config.yaml`:

```yaml
mcp_servers:
  garmin:
    url: "http://localhost:8000/mcp"
    transport: "streamable-http"
```

### Stdio Transport

If your client only supports stdio, you can run directly:

```json
{
  "mcpServers": {
    "garmin": {
      "command": "python",
      "args": ["path/to/garmin_mcp_server.py"]
    }
  }
}
```

## Example Queries

Once connected, ask your AI things like:

- "How did I sleep last night?"
- "What's my resting heart rate trend this week?"
- "Show me my last 5 strength training sessions with sets and reps"
- "Compare my sleep this week vs last week"
- "What's my body battery at right now?"
- "Give me a full weekly health report"
- "How many steps have I averaged this month?"

## Project Structure

```
├── garmin_mcp_server.py   # MCP server (34 tools)
├── garmin_auth.py         # One-time Garmin authentication
├── run_mcp_server.sh      # Server launch script
├── Dockerfile             # Container build
├── docker-compose.yml     # Docker Compose config
├── requirements.txt       # Python dependencies
└── LICENSE                # MIT
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GARMIN_EMAIL` | Garmin account email | No (interactive prompt fallback) |
| `GARMIN_PASSWORD` | Garmin account password | No (interactive prompt fallback) |
| `TZ` | Timezone (default: UTC) | No |

## Troubleshooting

**Authentication failed:** Run `python garmin_auth.py` to re-authenticate. Tokens may have expired.

**Empty data for some metrics:** Your Garmin device may not track that metric, or data hasn't synced yet.

**Connection refused:** Make sure the server is running and port 8000 is accessible. For Docker, check `docker compose logs`.

## Built With

- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server framework
- [garminconnect](https://github.com/cyberjunky/python-garminconnect) — Garmin Connect API client

## License

MIT — see [LICENSE](LICENSE)
