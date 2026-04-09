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
pip install 'garminconnect>=0.2.20,<0.3'
python garmin_auth.py
# If you hit a 429 from Cloudflare, use the browser-assisted fallback instead:
#   python garmin_browser_auth.py
# (see "Browser-assisted login" under Authentication below)

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

> **Note on `garminconnect` version:** `requirements.txt` pins to `<0.3`. The 0.3.x release rewrote the login flow with new strategies that Cloudflare currently 429s, and it also removed the `client.garth` attribute this repo relies on. Stay on `0.2.x` until the upstream situation settles.

### Browser-assisted login (Cloudflare fallback)

If `garmin_auth.py` fails with `429 Too Many Requests` from `sso.garmin.com`, Garmin's Cloudflare is blocking the scripted login POST from your IP. Use the browser-assisted fallback instead:

```bash
python garmin_browser_auth.py
```

This script:
1. Opens Garmin's SSO sign-in page in your real browser (which Cloudflare allows)
2. You sign in normally — MFA works natively because the browser handles it
3. You paste the post-login `ticket=ST-...` value back into the script
4. The script exchanges the ticket for OAuth1/OAuth2 tokens via `connectapi.garmin.com` (a different host that isn't Cloudflare-walled) and writes the same `~/.garminconnect/oauth1_token.json` and `oauth2_token.json` files that `garmin_auth.py` produces

No other code needs to change — `garmin_mcp_server.py` loads the resulting tokens the same way. The most reliable way to grab the ticket is to open Chrome DevTools → Network tab → enable "Preserve log" **before** clicking Sign In, then inspect the response body of the `POST /sso/signin` request and copy the `ST-...` value.

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
├── garmin_mcp_server.py     # MCP server (34 tools)
├── garmin_auth.py           # One-time Garmin authentication
├── garmin_browser_auth.py   # Browser-assisted auth fallback (Cloudflare 429 workaround)
├── run_mcp_server.sh        # Server launch script
├── Dockerfile               # Container build
├── docker-compose.yml       # Docker Compose config
├── requirements.txt         # Python dependencies
└── LICENSE                  # MIT
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GARMIN_EMAIL` | Garmin account email | No (interactive prompt fallback) |
| `GARMIN_PASSWORD` | Garmin account password | No (interactive prompt fallback) |
| `TZ` | Timezone (default: UTC) | No |

## Troubleshooting

**Authentication failed:** Run `python garmin_auth.py` to re-authenticate. Tokens may have expired.

**`429 Too Many Requests` on login:** Garmin's Cloudflare is rate-limiting the scripted login POST to `sso.garmin.com/sso/signin`. Use `python garmin_browser_auth.py` instead (see the [Browser-assisted login](#browser-assisted-login-cloudflare-fallback) section) — it signs you in via your real browser and then exchanges the SSO ticket against `connectapi.garmin.com`, which isn't blocked the same way. Also make sure you're on `garminconnect<0.3` — the 0.3.x rewrite hits the same wall with every strategy it tries.

**`AttributeError: 'Garmin' object has no attribute 'garth'`:** You're on `garminconnect>=0.3.0`, which dropped the `garth` attribute this repo uses. Downgrade with `pip install 'garminconnect>=0.2.20,<0.3'`.

**Empty data for some metrics:** Your Garmin device may not track that metric, or data hasn't synced yet.

**Connection refused:** Make sure the server is running and port 8000 is accessible. For Docker, check `docker compose logs`.

## Built With

- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server framework
- [garminconnect](https://github.com/cyberjunky/python-garminconnect) — Garmin Connect API client

## License

MIT — see [LICENSE](LICENSE)
