#!/usr/bin/env python3
"""
Garmin Connect MCP Server
Exposes Garmin health and fitness data to AI models via Model Context Protocol
"""

import os
import json
import logging
import concurrent.futures
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastmcp import FastMCP, Context
from garminconnect import Garmin, GarminConnectAuthenticationError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("garmin_mcp")

# Token storage directory
TOKEN_DIR = Path.home() / ".garminconnect"

# Global client instance
_garmin_client: Optional[Garmin] = None

# Conversion constants
KM_TO_MILES = 0.621371
METERS_TO_MILES = 0.000621371

# Thread pool for parallel Garmin API calls (synchronous library)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def km_to_miles(km: float) -> float:
    """Convert kilometers to miles."""
    return round(km * KM_TO_MILES, 2)


def meters_to_miles(meters: float) -> float:
    """Convert meters to miles."""
    return round(meters * METERS_TO_MILES, 2)


def _parallel_fetch(tasks: list) -> list:
    """
    Run a list of (fn, *args) tuples in parallel using the thread pool.
    Returns results in the same order. None is returned for any task that raises.

    Args:
        tasks: list of (callable, *positional_args) tuples
    """
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for task in tasks:
            fn, *args = task
            futures.append(pool.submit(fn, *args))

    results = []
    for f in futures:
        try:
            results.append(f.result())
        except Exception as e:
            logger.warning(f"Parallel fetch task failed: {e}")
            results.append(None)
    return results


def _ts_to_readable(ts_ms) -> Optional[str]:
    """Convert a millisecond timestamp to a human-readable local time string."""
    if not ts_ms:
        return None
    try:
        return datetime.fromtimestamp(int(ts_ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def get_garmin_client() -> Garmin:
    """Get or create the Garmin client with authentication."""
    global _garmin_client

    if _garmin_client is not None:
        return _garmin_client

    # Try to load from existing tokens first
    token_file = TOKEN_DIR / "oauth1_token.json"

    if token_file.exists():
        try:
            client = Garmin()
            client.login(str(TOKEN_DIR))
            _garmin_client = client
            return client
        except Exception as e:
            raise RuntimeError(
                f"Failed to authenticate with stored tokens: {e}. "
                "Run 'python garmin_auth.py' to re-authenticate."
            )

    # Try environment variables
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if email and password:
        try:
            client = Garmin(email, password)
            client.login()
            client.garth.dump(TOKEN_DIR)
            _garmin_client = client
            return client
        except GarminConnectAuthenticationError as e:
            raise RuntimeError(f"Authentication failed: {e}")

    raise RuntimeError(
        "No Garmin authentication found. Either:\n"
        "1. Run 'python garmin_auth.py' to authenticate interactively, or\n"
        "2. Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables"
    )


# Create the MCP server
mcp = FastMCP(
    "Garmin Connect",
    instructions="""You have access to the user's Garmin health and fitness data.
    Use these tools to answer questions about their health metrics, activities, sleep, stress, and more.
    Always specify dates in YYYY-MM-DD format. Use 'today' for current date queries.
    When asked about trends or comparisons, use the date range tools to get multiple days of data.
    For a comprehensive weekly health report, use get_weekly_health_report which returns 7 days of data in one call."""
)


@mcp.tool
def get_todays_summary() -> dict:
    """
    Get a comprehensive health summary for today including steps, heart rate,
    sleep, stress, and body battery.
    """
    client = get_garmin_client()
    today = date.today().isoformat()

    summary = {"date": today}

    # Daily stats
    try:
        stats = client.get_stats(today)
        if stats:
            summary["steps"] = stats.get("totalSteps", 0)
            summary["step_goal"] = stats.get("dailyStepGoal", 0)
            distance_km = round(stats.get("totalDistanceMeters", 0) / 1000, 2)
            summary["distance_km"] = distance_km
            summary["distance_miles"] = km_to_miles(distance_km)
            summary["active_calories"] = stats.get("activeKilocalories", 0)
            summary["total_calories"] = stats.get("totalKilocalories", 0)
            summary["floors_climbed"] = stats.get("floorsAscended", 0)
            summary["intensity_minutes"] = stats.get("intensityMinutes", 0)
    except Exception as e:
        logger.warning(f"Failed to get daily stats for today: {e}")

    # Heart rate
    try:
        hr = client.get_heart_rates(today)
        if hr:
            summary["resting_heart_rate"] = hr.get("restingHeartRate")
            summary["min_heart_rate"] = hr.get("minHeartRate")
            summary["max_heart_rate"] = hr.get("maxHeartRate")
    except Exception as e:
        logger.warning(f"Failed to get heart rate for today: {e}")

    # Sleep (from previous night)
    try:
        sleep_data = client.get_sleep_data(today)
        if sleep_data:
            daily = sleep_data.get("dailySleepDTO", {})
            sleep_seconds = daily.get("sleepTimeSeconds", 0)
            summary["sleep_hours"] = round(sleep_seconds / 3600, 1) if sleep_seconds else None
            summary["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
            summary["deep_sleep_hours"] = round(daily.get("deepSleepSeconds", 0) / 3600, 1)
            summary["rem_sleep_hours"] = round(daily.get("remSleepSeconds", 0) / 3600, 1)
    except Exception as e:
        logger.warning(f"Failed to get sleep data for today: {e}")

    # Stress
    try:
        stress = client.get_stress_data(today)
        if stress:
            summary["stress_avg"] = stress.get("avgStressLevel")
            summary["stress_max"] = stress.get("maxStressLevel")
    except Exception as e:
        logger.warning(f"Failed to get stress data for today: {e}")

    # Body battery
    try:
        bb = client.get_body_battery(today)
        if bb and isinstance(bb, list) and len(bb) > 0:
            bb_data = bb[0]
            summary["body_battery_charged"] = bb_data.get("charged")
            summary["body_battery_drained"] = bb_data.get("drained")
            bb_values = bb_data.get("bodyBatteryValuesArray", [])
            if bb_values:
                levels = [v[1] for v in bb_values if len(v) > 1]
                if levels:
                    summary["body_battery_current"] = levels[-1]
                    summary["body_battery_high"] = max(levels)
                    summary["body_battery_low"] = min(levels)
    except Exception as e:
        logger.warning(f"Failed to get body battery for today: {e}")

    return summary


@mcp.tool
def get_daily_stats(date_str: str = "today") -> dict:
    """
    Get daily activity stats (steps, calories, distance, floors) for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        stats = client.get_stats(date_str)
        if stats:
            distance_meters = stats.get("totalDistanceMeters", 0)
            distance_km = round(distance_meters / 1000, 2)
            return {
                "date": date_str,
                "steps": stats.get("totalSteps", 0),
                "step_goal": stats.get("dailyStepGoal", 0),
                "distance_meters": distance_meters,
                "distance_km": distance_km,
                "distance_miles": km_to_miles(distance_km),
                "active_calories": stats.get("activeKilocalories", 0),
                "total_calories": stats.get("totalKilocalories", 0),
                "floors_climbed": stats.get("floorsAscended", 0),
                "floors_descended": stats.get("floorsDescended", 0),
                "intensity_minutes": stats.get("intensityMinutes", 0),
                "moderate_intensity_minutes": stats.get("moderateIntensityMinutes", 0),
                "vigorous_intensity_minutes": stats.get("vigorousIntensityMinutes", 0),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_heart_rate(date_str: str = "today") -> dict:
    """
    Get heart rate data for a specific date including resting HR and time in zones.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        hr = client.get_heart_rates(date_str)
        if hr:
            result = {
                "date": date_str,
                "resting_heart_rate": hr.get("restingHeartRate"),
                "min_heart_rate": hr.get("minHeartRate"),
                "max_heart_rate": hr.get("maxHeartRate"),
            }

            # Heart rate zones
            zones = hr.get("heartRateTimeInZones", [])
            if zones:
                result["time_in_zones"] = {
                    zone.get("zoneName", f"Zone {i}"): round(zone.get("secsInZone", 0) / 60, 1)
                    for i, zone in enumerate(zones)
                }

            return result
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_sleep(date_str: str = "today") -> dict:
    """
    Get sleep data for a specific date including duration, stages, sleep score,
    avg heart rate, awake count, and sleep stress.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        sleep_data = client.get_sleep_data(date_str)
        if sleep_data:
            daily = sleep_data.get("dailySleepDTO", {})
            sleep_seconds = daily.get("sleepTimeSeconds", 0)

            # Human-readable start/end times
            start_ts = daily.get("sleepStartTimestampLocal") or daily.get("sleepStartTimestampGMT")
            end_ts = daily.get("sleepEndTimestampLocal") or daily.get("sleepEndTimestampGMT")

            return {
                "date": date_str,
                "sleep_start_timestamp": start_ts,
                "sleep_end_timestamp": end_ts,
                "sleep_start_time": _ts_to_readable(start_ts),
                "sleep_end_time": _ts_to_readable(end_ts),
                "total_sleep_hours": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
                "deep_sleep_hours": round((daily.get("deepSleepSeconds") or 0) / 3600, 2),
                "light_sleep_hours": round((daily.get("lightSleepSeconds") or 0) / 3600, 2),
                "rem_sleep_hours": round((daily.get("remSleepSeconds") or 0) / 3600, 2),
                "awake_hours": round((daily.get("awakeSleepSeconds") or 0) / 3600, 2),
                "awake_count": daily.get("awakeSleepCount") or daily.get("awakeCount"),
                "sleep_score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
                "avg_heart_rate": daily.get("averageHeartRate") or daily.get("avgHeartRate"),
                "avg_sleep_stress": daily.get("avgSleepStress"),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_stress(date_str: str = "today") -> dict:
    """
    Get stress data for a specific date including overall level and time at different stress levels.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        stress = client.get_stress_data(date_str)
        if stress:
            return {
                "date": date_str,
                "avg_stress_level": stress.get("avgStressLevel"),
                "max_stress_level": stress.get("maxStressLevel"),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_body_battery(date_str: str = "today") -> dict:
    """
    Get body battery data for a specific date showing energy levels throughout the day.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        bb = client.get_body_battery(date_str)
        if bb and isinstance(bb, list) and len(bb) > 0:
            bb_data = bb[0]  # First element contains the data
            result = {
                "date": date_str,
                "charged": bb_data.get("charged"),
                "drained": bb_data.get("drained"),
            }
            # Extract levels from bodyBatteryValuesArray
            bb_values = bb_data.get("bodyBatteryValuesArray", [])
            if bb_values:
                levels = [v[1] for v in bb_values if len(v) > 1]
                if levels:
                    result["current_level"] = levels[-1]
                    result["high"] = max(levels)
                    result["low"] = min(levels)
            return result
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_hrv(date_str: str = "today") -> dict:
    """
    Get Heart Rate Variability (HRV) data for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        hrv = client.get_hrv_data(date_str)
        if hrv:
            summary = hrv.get("hrvSummary", {})
            return {
                "date": date_str,
                "weekly_average": summary.get("weeklyAvg"),
                "last_night_average": summary.get("lastNightAvg"),
                "last_night_5min_high": summary.get("lastNight5MinHigh"),
                "status": summary.get("status"),
                "feedback": summary.get("feedbackPhrase"),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_spo2(date_str: str = "today") -> dict:
    """
    Get blood oxygen (SpO2) data for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        spo2 = client.get_spo2_data(date_str)
        if spo2:
            return {
                "date": date_str,
                "average_spo2": spo2.get("averageSpO2"),
                "lowest_spo2": spo2.get("lowestSpO2"),
                "latest_spo2": spo2.get("latestSpO2"),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_respiration(date_str: str = "today") -> dict:
    """
    Get respiration data for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today' for current date
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        resp = client.get_respiration_data(date_str)
        if resp:
            return {
                "date": date_str,
                "avg_waking_respiration": resp.get("avgWakingRespirationValue"),
                "highest_respiration": resp.get("highestRespirationValue"),
                "lowest_respiration": resp.get("lowestRespirationValue"),
                "avg_sleep_respiration": resp.get("avgSleepRespirationValue"),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_recent_activities(limit: int = 10) -> list:
    """
    Get recent activities/workouts.

    Args:
        limit: Number of activities to retrieve (default 10, max 100)
    """
    client = get_garmin_client()
    limit = min(max(1, limit), 100)

    try:
        activities = client.get_activities(0, limit)
        if activities:
            result = []
            for activity in activities:
                distance_km = round(activity.get("distance", 0) / 1000, 2)
                act = {
                    "id": activity.get("activityId"),
                    "name": activity.get("activityName"),
                    "type": activity.get("activityType", {}).get("typeKey"),
                    "date": activity.get("startTimeLocal"),
                    "duration_minutes": round(activity.get("duration", 0) / 60, 1),
                    "distance_km": distance_km,
                    "distance_miles": km_to_miles(distance_km),
                    "calories": activity.get("calories"),
                    "avg_heart_rate": activity.get("averageHR"),
                    "max_heart_rate": activity.get("maxHR"),
                }

                # Calculate pace for running/walking activities
                avg_speed = activity.get("averageSpeed")
                if avg_speed and avg_speed > 0:
                    pace_min_per_km = 1000 / (avg_speed * 60)
                    pace_min_per_mile = 1609.344 / (avg_speed * 60)
                    act["avg_pace_per_km"] = f"{int(pace_min_per_km)}:{int((pace_min_per_km % 1) * 60):02d}"
                    act["avg_pace_per_mile"] = f"{int(pace_min_per_mile)}:{int((pace_min_per_mile % 1) * 60):02d}"

                result.append(act)
            return result
        return []
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
def get_last_activity() -> dict:
    """
    Get the most recent activity/workout — quick 'what did I just do' lookup.
    Returns a single activity with all key metrics.
    """
    client = get_garmin_client()

    try:
        last = client.get_last_activity()
        if not last:
            return {"error": "No recent activity found"}

        distance_km = round(last.get("distance", 0) / 1000, 2)
        avg_speed = last.get("averageSpeed")
        act = {
            "id": last.get("activityId"),
            "name": last.get("activityName"),
            "type": last.get("activityType", {}).get("typeKey"),
            "date": last.get("startTimeLocal"),
            "duration_minutes": round(last.get("duration", 0) / 60, 1),
            "distance_km": distance_km,
            "distance_miles": km_to_miles(distance_km),
            "calories": last.get("calories"),
            "avg_heart_rate": last.get("averageHR"),
            "max_heart_rate": last.get("maxHR"),
            "training_effect_aerobic": last.get("aerobicTrainingEffect"),
            "training_effect_anaerobic": last.get("anaerobicTrainingEffect"),
        }
        if avg_speed and avg_speed > 0:
            pace_min_per_km = 1000 / (avg_speed * 60)
            pace_min_per_mile = 1609.344 / (avg_speed * 60)
            act["avg_pace_per_km"] = f"{int(pace_min_per_km)}:{int((pace_min_per_km % 1) * 60):02d}"
            act["avg_pace_per_mile"] = f"{int(pace_min_per_mile)}:{int((pace_min_per_mile % 1) * 60):02d}"
        return act
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_activity_exercise_sets(activity_id: int) -> dict:
    """
    Get exercise sets, reps, and weight for a strength training activity.
    This exposes the actual workout data (sets/reps/weight) for lifting sessions.

    Args:
        activity_id: The activity ID (get from get_recent_activities or get_activities_by_type)
    """
    client = get_garmin_client()

    try:
        raw = client.get_activity_exercise_sets(activity_id)
        if not raw:
            return {"activity_id": activity_id, "exercises": [], "error": "No exercise data found"}

        # raw is typically a dict with an "exerciseSets" list
        exercise_sets = raw.get("exerciseSets", []) if isinstance(raw, dict) else raw

        # Group sets by exercise name/category
        exercises_map: dict = {}
        for s in exercise_sets:
            # Each set has category, exercise info, and the actual set data
            category = s.get("exerciseCategory") or s.get("category") or "Unknown"
            exercise_name = (
                s.get("exercises", [{}])[0].get("exerciseName")
                if s.get("exercises")
                else s.get("exerciseName") or category
            )
            key = exercise_name or category

            if key not in exercises_map:
                exercises_map[key] = {
                    "name": exercise_name or category,
                    "category": category,
                    "sets": [],
                }

            set_num = len(exercises_map[key]["sets"]) + 1
            reps = s.get("repetitionCount") or s.get("reps")
            weight_g = s.get("weight")  # garmin stores in grams
            weight_kg = round(weight_g / 1000, 2) if weight_g else None
            weight_lb = round(weight_kg * 2.20462, 1) if weight_kg else None
            duration_sec = s.get("duration") or s.get("durationInSeconds")

            exercises_map[key]["sets"].append({
                "set_number": set_num,
                "reps": reps,
                "weight_kg": weight_kg,
                "weight_lb": weight_lb,
                "duration_seconds": duration_sec,
            })

        return {
            "activity_id": activity_id,
            "exercises": list(exercises_map.values()),
        }
    except Exception as e:
        logger.warning(f"Failed to get exercise sets for activity {activity_id}: {e}")
        return {"activity_id": activity_id, "exercises": [], "error": str(e)}


@mcp.tool
def get_body_battery_events(date_str: str = "today") -> dict:
    """
    Get body battery events showing what caused energy changes throughout the day
    (activities, stress events, rest periods).

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today'
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        events = client.get_body_battery_events(date_str)
        if not events:
            return {"date": date_str, "events": [], "error": "No body battery event data"}

        # Normalise the event list
        event_list = events if isinstance(events, list) else events.get("bodyBatteryFeedbackList", [])
        formatted = []
        for ev in event_list:
            # Garmin nests event metadata under an "event" key
            inner = ev.get("event", {}) if isinstance(ev.get("event"), dict) else ev
            # Calculate end time from start + duration
            start_gmt = inner.get("eventStartTimeGmt")
            duration_ms = inner.get("durationInMilliseconds", 0)
            tz_offset_ms = inner.get("timezoneOffset", 0)

            # Parse start time
            start_local = None
            end_local = None
            if start_gmt:
                try:
                    from datetime import datetime as dt_cls
                    start_dt = dt_cls.strptime(start_gmt.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                    # Apply timezone offset (negative = behind UTC)
                    start_dt = start_dt + timedelta(milliseconds=tz_offset_ms)
                    start_local = start_dt.strftime("%Y-%m-%d %H:%M")
                    if duration_ms:
                        end_dt = start_dt + timedelta(milliseconds=duration_ms)
                        end_local = end_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            formatted.append({
                "event_type": inner.get("eventType"),
                "start_time": start_local,
                "end_time": end_local,
                "duration_minutes": round(duration_ms / 60000, 1) if duration_ms else None,
                "body_battery_impact": inner.get("bodyBatteryImpact"),
                "feedback_type": inner.get("feedbackType"),
                "short_feedback": inner.get("shortFeedback"),
                "activity_name": ev.get("activityName"),
                "activity_type": ev.get("activityType"),
                "avg_stress": round(ev.get("averageStress", 0), 1) if ev.get("averageStress") else None,
            })

        return {"date": date_str, "events": formatted}
    except Exception as e:
        logger.warning(f"Failed to get body battery events for {date_str}: {e}")
        return {"date": date_str, "events": [], "error": str(e)}


@mcp.tool
def get_training_status() -> dict:
    """
    Get current training status including VO2 max, training load, and fitness metrics.
    """
    client = get_garmin_client()
    today = date.today().isoformat()

    try:
        status = client.get_training_status(today)
        if status:
            # Extract from nested objects if present
            vo2_max_obj = status.get("mostRecentVO2Max", {}) if isinstance(status.get("mostRecentVO2Max"), dict) else {}
            training_status_obj = status.get("mostRecentTrainingStatus", {}) if isinstance(status.get("mostRecentTrainingStatus"), dict) else {}
            load_balance_obj = status.get("mostRecentTrainingLoadBalance", {}) if isinstance(status.get("mostRecentTrainingLoadBalance"), dict) else {}

            return {
                "training_status": training_status_obj.get("trainingStatusLabel") or training_status_obj.get("trainingStatusKey"),
                "vo2_max": vo2_max_obj.get("vo2MaxValue") or vo2_max_obj.get("vo2Max"),
                "weekly_load": load_balance_obj.get("weeklyLoadTotal"),
                "acute_load": load_balance_obj.get("acuteLoad"),
                "chronic_load": load_balance_obj.get("chronicLoad"),
            }
        return {"error": "No training status available"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_training_readiness() -> dict:
    """
    Get current training readiness score and recovery information.
    """
    client = get_garmin_client()
    today = date.today().isoformat()

    try:
        readiness_list = client.get_training_readiness(today)
        if readiness_list and isinstance(readiness_list, list) and len(readiness_list) > 0:
            readiness = readiness_list[0]
            return {
                "date": readiness.get("calendarDate"),
                "score": readiness.get("score"),
                "level": readiness.get("level"),
                "feedback": readiness.get("feedbackShort"),
                "recovery_time_hours": readiness.get("recoveryTime"),
                "sleep_score": readiness.get("sleepScore"),
                "hrv_feedback": readiness.get("hrvFactorFeedback"),
            }
        return {"error": "No training readiness available"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_body_composition() -> dict:
    """
    Get latest body composition data including weight, BMI, body fat percentage, etc.
    """
    client = get_garmin_client()
    today = date.today().isoformat()
    start = (date.today() - timedelta(days=90)).isoformat()

    try:
        # Try weight API first (more reliable)
        try:
            weight_data = client.get_weigh_ins(start, today)
            if weight_data and len(weight_data) > 0:
                latest = weight_data[0]  # Most recent
                weight_kg = latest.get("weight") / 1000 if latest.get("weight") else None

                return {
                    "weight_kg": round(weight_kg, 2) if weight_kg else None,
                    "weight_lb": round(weight_kg * 2.20462, 2) if weight_kg else None,
                    "bmi": latest.get("bmi"),
                    "body_fat_percent": latest.get("bodyFatPercentage"),
                    "body_water_percent": latest.get("bodyWaterPercentage"),
                    "bone_mass_kg": latest.get("boneMassInGrams", 0) / 1000 if latest.get("boneMassInGrams") else None,
                    "muscle_mass_kg": latest.get("muscleMassInGrams", 0) / 1000 if latest.get("muscleMassInGrams") else None,
                }
        except Exception as e:
            logger.warning(f"Failed to get weigh-ins, falling back to body_composition: {e}")

        # Fallback to body composition API
        bc = client.get_body_composition(start, today)
        if bc and isinstance(bc, list) and len(bc) > 0:
            latest = bc[-1]  # Get most recent entry
            weight_g = latest.get("weight", 0)
            weight_kg = weight_g / 1000 if weight_g else None
            weight_lb = weight_kg * 2.20462 if weight_kg else None

            return {
                "weight_kg": round(weight_kg, 1) if weight_kg else None,
                "weight_lb": round(weight_lb, 1) if weight_lb else None,
                "bmi": latest.get("bmi"),
                "body_fat_percent": latest.get("bodyFat"),
                "body_water_percent": latest.get("bodyWater"),
                "bone_mass_kg": latest.get("boneMass"),
                "muscle_mass_kg": latest.get("muscleMass"),
            }

        return {"error": "No body composition data available"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_personal_records() -> list:
    """
    Get personal records/bests for various activities.
    """
    client = get_garmin_client()

    try:
        records = client.get_personal_record()
        if records:
            result = []
            for record in records[:20]:
                # Try multiple possible field names
                record_type = (
                    record.get("typeKey") or
                    record.get("prType") or
                    record.get("recordType") or
                    "Unknown"
                )

                # Convert timestamp if it's in milliseconds
                date_value = record.get("prStartTimeLocal") or record.get("prStartTime") or record.get("startTime")
                if date_value and isinstance(date_value, int):
                    # Convert milliseconds to date string
                    date_value = datetime.fromtimestamp(date_value / 1000).strftime("%Y-%m-%d")

                result.append({
                    "type": record_type,
                    "value": record.get("value"),
                    "date": date_value,
                    "unit": record.get("metricKey"),
                })
            return result
        return []
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
def get_devices() -> list:
    """
    Get information about connected Garmin devices.
    """
    client = get_garmin_client()

    try:
        devices = client.get_devices()
        if devices:
            return [
                {
                    "name": device.get("productDisplayName"),
                    "unit_id": device.get("unitId"),
                    "software_version": device.get("softwareVersion"),
                    "last_synced": device.get("lastSyncTime"),
                }
                for device in devices
            ]
        return []
    except Exception as e:
        return [{"error": str(e)}]


def _fetch_day_metrics(client: Garmin, date_str: str, metrics: list) -> dict:
    """Fetch all requested metrics for a single date. Runs synchronously (called from thread pool)."""
    day_data = {"date": date_str}

    if "steps" in metrics:
        try:
            stats = client.get_stats(date_str)
            if stats:
                day_data["steps"] = stats.get("totalSteps", 0)
                distance_km = round(stats.get("totalDistanceMeters", 0) / 1000, 2)
                day_data["distance_km"] = distance_km
                day_data["distance_miles"] = km_to_miles(distance_km)
                day_data["calories"] = stats.get("totalKilocalories", 0)
        except Exception as e:
            logger.warning(f"Failed to get steps for {date_str}: {e}")

    if "heart_rate" in metrics:
        try:
            hr = client.get_heart_rates(date_str)
            if hr:
                day_data["resting_hr"] = hr.get("restingHeartRate")
        except Exception as e:
            logger.warning(f"Failed to get heart rate for {date_str}: {e}")

    if "sleep" in metrics:
        try:
            sleep_data = client.get_sleep_data(date_str)
            if sleep_data:
                daily = sleep_data.get("dailySleepDTO", {})
                sleep_sec = daily.get("sleepTimeSeconds", 0)
                day_data["sleep_hours"] = round(sleep_sec / 3600, 1) if sleep_sec else None
                day_data["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
        except Exception as e:
            logger.warning(f"Failed to get sleep for {date_str}: {e}")

    if "stress" in metrics:
        try:
            stress = client.get_stress_data(date_str)
            if stress:
                day_data["stress_avg"] = stress.get("avgStressLevel")
                day_data["stress_max"] = stress.get("maxStressLevel")
        except Exception as e:
            logger.warning(f"Failed to get stress for {date_str}: {e}")

    if "body_battery" in metrics:
        try:
            bb = client.get_body_battery(date_str)
            if bb and isinstance(bb, list) and len(bb) > 0:
                bb_data = bb[0]
                bb_values = bb_data.get("bodyBatteryValuesArray", [])
                if bb_values:
                    levels = [v[1] for v in bb_values if len(v) > 1]
                    if levels:
                        day_data["body_battery_high"] = max(levels)
                        day_data["body_battery_low"] = min(levels)
        except Exception as e:
            logger.warning(f"Failed to get body battery for {date_str}: {e}")

    if "hrv" in metrics:
        try:
            hrv = client.get_hrv_data(date_str)
            if hrv:
                day_data["hrv"] = hrv.get("hrvSummary", {}).get("lastNightAvg")
        except Exception as e:
            logger.warning(f"Failed to get HRV for {date_str}: {e}")

    if "spo2" in metrics:
        try:
            spo2 = client.get_spo2_data(date_str)
            if spo2:
                day_data["spo2_avg"] = spo2.get("averageSpO2")
                day_data["spo2_lowest"] = spo2.get("lowestSpO2")
        except Exception as e:
            logger.warning(f"Failed to get SpO2 for {date_str}: {e}")

    if "respiration" in metrics:
        try:
            resp = client.get_respiration_data(date_str)
            if resp:
                day_data["respiration_avg_waking"] = resp.get("avgWakingRespirationValue")
                day_data["respiration_avg_sleep"] = resp.get("avgSleepRespirationValue")
        except Exception as e:
            logger.warning(f"Failed to get respiration for {date_str}: {e}")

    return day_data


@mcp.tool
def get_health_data_for_date_range(
    start_date: str,
    end_date: str,
    metrics: list[str] = ["steps", "sleep", "stress", "heart_rate"]
) -> list:
    """
    Get health data for a date range. Useful for analyzing trends.
    Uses parallel fetching for performance.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        metrics: List of metrics to include. Options: steps, sleep, stress, heart_rate, body_battery, hrv, spo2, respiration
    """
    client = get_garmin_client()

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return [{"error": "Invalid date format. Use YYYY-MM-DD"}]

    if start > end:
        return [{"error": "Start date must be before end date"}]

    if (end - start).days > 90:
        return [{"error": "Date range cannot exceed 90 days"}]

    # Build list of dates
    date_strs = []
    current = start
    while current <= end:
        date_strs.append(current.isoformat())
        current += timedelta(days=1)

    # Fetch all days in parallel
    tasks = [(_fetch_day_metrics, client, d, metrics) for d in date_strs]
    results = _parallel_fetch(tasks)

    # Replace None results with placeholder
    final = []
    for i, r in enumerate(results):
        if r is None:
            final.append({"date": date_strs[i], "error": "fetch failed"})
        else:
            final.append(r)
    return final


@mcp.tool
def get_weekly_summary() -> dict:
    """
    Get a summary of health metrics for the past 7 days with averages and totals.
    Uses parallel fetching for performance.
    """
    client = get_garmin_client()
    end = date.today()
    start = end - timedelta(days=6)

    date_strs = []
    current = start
    while current <= end:
        date_strs.append(current.isoformat())
        current += timedelta(days=1)

    def _fetch_summary_day(date_str):
        day = {"date": date_str}
        try:
            stats = client.get_stats(date_str)
            if stats:
                day["steps"] = stats.get("totalSteps", 0)
        except Exception as e:
            logger.warning(f"Failed to get stats for {date_str}: {e}")
            day["steps"] = 0

        try:
            hr = client.get_heart_rates(date_str)
            if hr:
                day["resting_hr"] = hr.get("restingHeartRate")
        except Exception as e:
            logger.warning(f"Failed to get HR for {date_str}: {e}")

        try:
            sleep_data = client.get_sleep_data(date_str)
            if sleep_data:
                daily = sleep_data.get("dailySleepDTO", {})
                sleep_sec = daily.get("sleepTimeSeconds", 0)
                day["sleep_hours"] = round(sleep_sec / 3600, 1) if sleep_sec else None
        except Exception as e:
            logger.warning(f"Failed to get sleep for {date_str}: {e}")

        return day

    tasks = [(_fetch_summary_day, d) for d in date_strs]
    raw_results = _parallel_fetch(tasks)
    data = [r if r is not None else {"date": date_strs[i]} for i, r in enumerate(raw_results)]

    # Calculate summary
    steps = [d.get("steps", 0) for d in data]
    hrs = [d.get("resting_hr") for d in data if d.get("resting_hr")]
    sleep = [d.get("sleep_hours") for d in data if d.get("sleep_hours")]

    return {
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "total_steps": sum(steps),
        "avg_daily_steps": round(sum(steps) / len(steps)) if steps else 0,
        "best_step_day": max(steps) if steps else 0,
        "avg_resting_hr": round(sum(hrs) / len(hrs)) if hrs else None,
        "avg_sleep_hours": round(sum(sleep) / len(sleep), 1) if sleep else None,
        "daily_data": data,
    }


# =============================================================================
# EXTENDED TOOLS - Weight, Activities, Goals, Insights
# =============================================================================

@mcp.tool
def get_weight_history(days: int = 30) -> dict:
    """
    Get weight and body composition history with trend analysis.

    Args:
        days: Number of days of history (default 30, max 365)
    """
    client = get_garmin_client()
    days = min(max(1, days), 365)

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()

    try:
        bc = client.get_body_composition(start, end)
        if not bc:
            return {"error": "No weight data available"}

        weights = bc.get("dateWeightList", [])
        if not weights:
            return {"error": "No weight measurements found"}

        # Process measurements
        measurements = []
        for w in weights:
            measurements.append({
                "date": w.get("calendarDate"),
                "weight_kg": round(w.get("weight", 0) / 1000, 2),
                "weight_lb": round(w.get("weight", 0) / 1000 * 2.20462, 1),
                "bmi": round(w.get("bmi", 0), 1) if w.get("bmi") else None,
                "body_fat_pct": w.get("bodyFat"),
                "muscle_mass_kg": round(w.get("muscleMass", 0) / 1000, 2) if w.get("muscleMass") else None,
                "body_water_pct": w.get("bodyWater"),
                "bone_mass_kg": round(w.get("boneMass", 0) / 1000, 2) if w.get("boneMass") else None,
            })

        # Calculate trends
        weight_values = [m["weight_kg"] for m in measurements if m["weight_kg"]]
        if len(weight_values) >= 2:
            trend = {
                "start_weight_kg": weight_values[-1],  # Oldest
                "current_weight_kg": weight_values[0],  # Most recent
                "change_kg": round(weight_values[0] - weight_values[-1], 2),
                "change_lb": round((weight_values[0] - weight_values[-1]) * 2.20462, 1),
                "min_kg": round(min(weight_values), 2),
                "max_kg": round(max(weight_values), 2),
                "avg_kg": round(sum(weight_values) / len(weight_values), 2),
            }
        else:
            trend = None

        # Get averages from API
        avg = bc.get("totalAverage", {})

        return {
            "period": f"{start} to {end}",
            "measurement_count": len(measurements),
            "measurements": measurements,
            "trend": trend,
            "averages": {
                "weight_kg": round(avg.get("weight", 0) / 1000, 2) if avg.get("weight") else None,
                "bmi": round(avg.get("bmi", 0), 1) if avg.get("bmi") else None,
                "body_fat_pct": avg.get("bodyFat"),
                "muscle_mass_kg": round(avg.get("muscleMass", 0) / 1000, 2) if avg.get("muscleMass") else None,
            }
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_activities_by_type(
    activity_type: str,
    limit: int = 20
) -> list:
    """
    Get activities filtered by type.

    Args:
        activity_type: Type of activity (running, cycling, walking, swimming, strength_training, hiking, etc.)
        limit: Number of activities to retrieve (max 100)
    """
    client = get_garmin_client()
    limit = min(max(1, limit), 100)

    try:
        # Get more activities to filter from
        activities = client.get_activities(0, limit * 3)
        if not activities:
            return []

        # Filter by type
        filtered = []
        for activity in activities:
            act_type = activity.get("activityType", {}).get("typeKey", "").lower()
            if activity_type.lower() in act_type or act_type in activity_type.lower():
                distance_km = round(activity.get("distance", 0) / 1000, 2)
                avg_speed = activity.get("averageSpeed", 0)
                act = {
                    "id": activity.get("activityId"),
                    "name": activity.get("activityName"),
                    "type": activity.get("activityType", {}).get("typeKey"),
                    "date": activity.get("startTimeLocal"),
                    "duration_minutes": round(activity.get("duration", 0) / 60, 1),
                    "distance_km": distance_km,
                    "distance_miles": km_to_miles(distance_km),
                    "calories": activity.get("calories"),
                    "avg_hr": activity.get("averageHR"),
                    "max_hr": activity.get("maxHR"),
                    "avg_speed_kmh": round(avg_speed * 3.6, 1) if avg_speed else None,
                    "avg_speed_mph": round(avg_speed * 2.23694, 1) if avg_speed else None,
                }

                # Add pace for running/walking
                if avg_speed and avg_speed > 0:
                    pace_km = 1000 / (avg_speed * 60)
                    pace_mile = 1609.344 / (avg_speed * 60)
                    act["avg_pace_min_km"] = f"{int(pace_km)}:{int((pace_km % 1) * 60):02d}"
                    act["avg_pace_min_mile"] = f"{int(pace_mile)}:{int((pace_mile % 1) * 60):02d}"

                # Add elevation if available
                if activity.get("elevationGain"):
                    act["elevation_gain_m"] = activity.get("elevationGain")
                    act["elevation_gain_ft"] = round(activity.get("elevationGain") * 3.28084, 0)

                filtered.append(act)

                if len(filtered) >= limit:
                    break

        return filtered
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
def get_activity_details(activity_id: int) -> dict:
    """
    Get detailed information about a specific activity including splits and laps.

    Args:
        activity_id: The activity ID (get from get_recent_activities or get_activities_by_type)
    """
    client = get_garmin_client()

    try:
        # Get activity details
        activity = client.get_activity(activity_id)
        if not activity:
            return {"error": "Activity not found"}

        # Data is nested in summaryDTO
        summary = activity.get("summaryDTO", {})
        act_type = activity.get("activityTypeDTO", {})

        distance_km = round(summary.get("distance", 0) / 1000, 2) if summary.get("distance") else None
        avg_speed = summary.get("averageSpeed", 0)
        max_speed = summary.get("maxSpeed", 0)
        elevation_gain = summary.get("elevationGain")
        elevation_loss = summary.get("elevationLoss")

        result = {
            "id": activity_id,
            "name": activity.get("activityName"),
            "type": act_type.get("typeKey"),
            "date": summary.get("startTimeLocal"),
            "duration_seconds": summary.get("duration"),
            "duration_formatted": None,
            "distance_km": distance_km,
            "distance_miles": km_to_miles(distance_km) if distance_km else None,
            "calories": summary.get("calories"),
            "avg_hr": summary.get("averageHR"),
            "max_hr": summary.get("maxHR"),
            "avg_speed_kmh": round(avg_speed * 3.6, 1) if avg_speed else None,
            "avg_speed_mph": round(avg_speed * 2.23694, 1) if avg_speed else None,
            "max_speed_kmh": round(max_speed * 3.6, 1) if max_speed else None,
            "max_speed_mph": round(max_speed * 2.23694, 1) if max_speed else None,
            "elevation_gain_m": elevation_gain,
            "elevation_gain_ft": round(elevation_gain * 3.28084, 0) if elevation_gain else None,
            "elevation_loss_m": elevation_loss,
            "elevation_loss_ft": round(elevation_loss * 3.28084, 0) if elevation_loss else None,
            "avg_cadence": summary.get("averageRunningCadenceInStepsPerMinute") or summary.get("averageBikingCadenceInRevPerMinute"),
            "avg_power": summary.get("avgPower"),
            "training_effect_aerobic": summary.get("trainingEffect"),
            "training_effect_anaerobic": summary.get("anaerobicTrainingEffect"),
            "vo2_max": summary.get("vO2MaxValue"),
        }

        # Add pace for running/walking activities
        if avg_speed and avg_speed > 0:
            pace_km = 1000 / (avg_speed * 60)
            pace_mile = 1609.344 / (avg_speed * 60)
            result["avg_pace_min_km"] = f"{int(pace_km)}:{int((pace_km % 1) * 60):02d}"
            result["avg_pace_min_mile"] = f"{int(pace_mile)}:{int((pace_mile % 1) * 60):02d}"

        # Format duration
        if result["duration_seconds"]:
            secs = result["duration_seconds"]
            hours = int(secs // 3600)
            mins = int((secs % 3600) // 60)
            s = int(secs % 60)
            result["duration_formatted"] = f"{hours}:{mins:02d}:{s:02d}" if hours else f"{mins}:{s:02d}"

        # Get splits/laps
        try:
            splits = client.get_activity_splits(activity_id)
            if splits and splits.get("lapDTOs"):
                result["laps"] = []
                for i, lap in enumerate(splits.get("lapDTOs", []), 1):
                    lap_distance_km = round(lap.get("distance", 0) / 1000, 2)
                    result["laps"].append({
                        "lap": i,
                        "distance_km": lap_distance_km,
                        "distance_miles": km_to_miles(lap_distance_km),
                        "duration_seconds": lap.get("duration"),
                        "avg_hr": lap.get("averageHR"),
                        "max_hr": lap.get("maxHR"),
                        "calories": lap.get("calories"),
                    })
        except Exception as e:
            logger.warning(f"Failed to get splits for activity {activity_id}: {e}")

        # Get HR zones
        try:
            hr_zones = client.get_activity_hr_in_timezones(activity_id)
            if hr_zones:
                result["hr_zones"] = [
                    {
                        "zone": z.get("zoneName") or f"Zone {z.get('zoneNumber', i)}",
                        "seconds": z.get("secsInZone", 0),
                        "minutes": round(z.get("secsInZone", 0) / 60, 1),
                    }
                    for i, z in enumerate(hr_zones, 1)
                ]
        except Exception as e:
            logger.warning(f"Failed to get HR zones for activity {activity_id}: {e}")

        return result
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def search_activities(
    query: str = "",
    start_date: str = "",
    end_date: str = "",
    min_distance_km: float = 0,
    min_duration_minutes: float = 0,
    limit: int = 50
) -> list:
    """
    Search and filter activities with multiple criteria.

    Args:
        query: Search text in activity name (optional)
        start_date: Filter activities after this date YYYY-MM-DD (optional)
        end_date: Filter activities before this date YYYY-MM-DD (optional)
        min_distance_km: Minimum distance in km (optional)
        min_duration_minutes: Minimum duration in minutes (optional)
        limit: Maximum results (default 50, max 100)
    """
    client = get_garmin_client()
    limit = min(max(1, limit), 100)

    try:
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
    except ValueError:
        return [{"error": "Invalid date format. Use YYYY-MM-DD"}]

    try:
        # Get more activities to filter from
        activities = client.get_activities(0, limit * 3)
        if not activities:
            return []

        results = []
        for activity in activities:
            # Filter by query
            if query:
                name = (activity.get("activityName") or "").lower()
                act_type = activity.get("activityType", {}).get("typeKey", "").lower()
                if query.lower() not in name and query.lower() not in act_type:
                    continue

            # Filter by date
            if start_dt or end_dt:
                act_date_str = activity.get("startTimeLocal", "")[:10]
                try:
                    act_date = datetime.strptime(act_date_str, "%Y-%m-%d")
                    if start_dt and act_date < start_dt:
                        continue
                    if end_dt and act_date > end_dt:
                        continue
                except ValueError:
                    continue

            # Filter by distance
            distance_km = (activity.get("distance") or 0) / 1000
            if min_distance_km and distance_km < min_distance_km:
                continue

            # Filter by duration
            duration_min = (activity.get("duration") or 0) / 60
            if min_duration_minutes and duration_min < min_duration_minutes:
                continue

            results.append({
                "id": activity.get("activityId"),
                "name": activity.get("activityName"),
                "type": activity.get("activityType", {}).get("typeKey"),
                "date": activity.get("startTimeLocal"),
                "duration_minutes": round(duration_min, 1),
                "distance_km": round(distance_km, 2),
                "distance_miles": km_to_miles(distance_km),
                "calories": activity.get("calories"),
                "avg_hr": activity.get("averageHR"),
            })

            if len(results) >= limit:
                break

        return results
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
def get_daily_goals_progress(date_str: str = "today") -> dict:
    """
    Get progress toward daily goals (steps, intensity minutes, floors, etc.).

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today'
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        stats = client.get_stats(date_str)
        if not stats:
            return {"date": date_str, "error": "No data available"}

        steps = stats.get("totalSteps", 0)
        step_goal = stats.get("dailyStepGoal", 0)

        floors = stats.get("floorsAscended", 0)
        floor_goal = stats.get("floorsAscendedGoal", 0)

        intensity = stats.get("intensityMinutes", 0)
        intensity_goal = stats.get("intensityMinutesGoal", 0)

        return {
            "date": date_str,
            "steps": {
                "current": steps,
                "goal": step_goal,
                "remaining": max(0, step_goal - steps),
                "progress_pct": round(steps / step_goal * 100, 1) if step_goal else 0,
                "achieved": steps >= step_goal if step_goal else False,
            },
            "floors": {
                "current": floors,
                "goal": floor_goal,
                "remaining": max(0, floor_goal - floors) if floor_goal else None,
                "progress_pct": round(floors / floor_goal * 100, 1) if floor_goal else None,
            },
            "intensity_minutes": {
                "current": intensity,
                "goal": intensity_goal,
                "remaining": max(0, intensity_goal - intensity) if intensity_goal else None,
                "progress_pct": round(intensity / intensity_goal * 100, 1) if intensity_goal else None,
            },
            "calories": {
                "active": stats.get("activeKilocalories", 0),
                "total": stats.get("totalKilocalories", 0),
                "bmr": stats.get("bmrKilocalories", 0),
            },
            "distance_km": round(stats.get("totalDistanceMeters", 0) / 1000, 2),
            "distance_miles": meters_to_miles(stats.get("totalDistanceMeters", 0)),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_hydration(date_str: str = "today") -> dict:
    """
    Get hydration/water intake data for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today'
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        hydration = client.get_hydration_data(date_str)
        if hydration:
            goal_ml = hydration.get("goalInML") or 0
            intake_ml = hydration.get("valueInML") or 0

            return {
                "date": date_str,
                "intake_ml": intake_ml,
                "intake_oz": round(intake_ml * 0.033814, 1) if intake_ml else 0,
                "goal_ml": goal_ml,
                "goal_oz": round(goal_ml * 0.033814, 1) if goal_ml else 0,
                "remaining_ml": max(0, goal_ml - intake_ml),
                "progress_pct": round(intake_ml / goal_ml * 100, 1) if goal_ml else 0,
                "sweat_loss_ml": hydration.get("sweatLossInML") or 0,
            }
        return {"date": date_str, "error": "No hydration data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


def _get_period_stats(client: Garmin, start_str: str, end_str: str) -> Optional[dict]:
    """Fetch aggregated stats for a period using parallel per-day fetches."""
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    date_strs = []
    current = start
    while current <= end:
        date_strs.append(current.isoformat())
        current += timedelta(days=1)

    def fetch_one(date_str):
        row = {}
        try:
            stats = client.get_stats(date_str)
            if stats and stats.get("totalSteps"):
                row["steps"] = stats.get("totalSteps", 0)
        except Exception as e:
            logger.warning(f"compare_periods: failed stats for {date_str}: {e}")

        try:
            hr = client.get_heart_rates(date_str)
            if hr and hr.get("restingHeartRate"):
                row["resting_hr"] = hr.get("restingHeartRate")
        except Exception as e:
            logger.warning(f"compare_periods: failed HR for {date_str}: {e}")

        try:
            sleep = client.get_sleep_data(date_str)
            if sleep:
                daily = sleep.get("dailySleepDTO", {})
                if daily.get("sleepTimeSeconds"):
                    row["sleep_hours"] = daily.get("sleepTimeSeconds") / 3600
        except Exception as e:
            logger.warning(f"compare_periods: failed sleep for {date_str}: {e}")

        try:
            stress = client.get_stress_data(date_str)
            if stress and stress.get("avgStressLevel"):
                row["stress"] = stress.get("avgStressLevel")
        except Exception as e:
            logger.warning(f"compare_periods: failed stress for {date_str}: {e}")

        return row

    tasks = [(fetch_one, d) for d in date_strs]
    rows = _parallel_fetch(tasks)

    steps_list = [r["steps"] for r in rows if r and "steps" in r]
    sleep_list = [r["sleep_hours"] for r in rows if r and "sleep_hours" in r]
    hr_list = [r["resting_hr"] for r in rows if r and "resting_hr" in r]
    stress_list = [r["stress"] for r in rows if r and "stress" in r]

    return {
        "days": (end - start).days + 1,
        "steps_total": sum(steps_list),
        "steps_avg": round(sum(steps_list) / len(steps_list)) if steps_list else None,
        "sleep_avg_hours": round(sum(sleep_list) / len(sleep_list), 1) if sleep_list else None,
        "resting_hr_avg": round(sum(hr_list) / len(hr_list)) if hr_list else None,
        "stress_avg": round(sum(stress_list) / len(stress_list)) if stress_list else None,
    }


@mcp.tool
def compare_periods(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
) -> dict:
    """
    Compare health metrics between two time periods (e.g., this week vs last week).
    Uses parallel fetching for both periods.

    Args:
        period1_start: Start of first period (YYYY-MM-DD)
        period1_end: End of first period (YYYY-MM-DD)
        period2_start: Start of second period (YYYY-MM-DD)
        period2_end: End of second period (YYYY-MM-DD)
    """
    client = get_garmin_client()

    # Fetch both periods concurrently at the period level
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_get_period_stats, client, period1_start, period1_end)
        f2 = pool.submit(_get_period_stats, client, period2_start, period2_end)

    period1 = f1.result()
    period2 = f2.result()

    if not period1 or not period2:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

    def diff(a, b):
        if a is None or b is None:
            return None
        return round(a - b, 2)

    def pct_change(a, b):
        if a is None or b is None or b == 0:
            return None
        return round((a - b) / b * 100, 1)

    return {
        "period1": {"range": f"{period1_start} to {period1_end}", **period1},
        "period2": {"range": f"{period2_start} to {period2_end}", **period2},
        "comparison": {
            "steps_total_diff": diff(period1["steps_total"], period2["steps_total"]),
            "steps_avg_diff": diff(period1["steps_avg"], period2["steps_avg"]),
            "steps_pct_change": pct_change(period1["steps_total"], period2["steps_total"]),
            "sleep_avg_diff_hours": diff(period1["sleep_avg_hours"], period2["sleep_avg_hours"]),
            "resting_hr_diff": diff(period1["resting_hr_avg"], period2["resting_hr_avg"]),
            "stress_diff": diff(period1["stress_avg"], period2["stress_avg"]),
        }
    }


@mcp.tool
def get_badges() -> list:
    """
    Get earned badges and achievements.
    """
    client = get_garmin_client()

    try:
        badges = client.get_earned_badges()
        if badges:
            return [
                {
                    "name": badge.get("badgeName"),
                    "category": badge.get("badgeCategoryName"),
                    "earned_date": badge.get("badgeEarnedDate"),
                    "earned_number": badge.get("badgeEarnedNumber"),
                    "points": badge.get("badgePoints"),
                }
                for badge in badges[:50]
            ]
        return []
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
def get_floors_data(date_str: str = "today") -> dict:
    """
    Get detailed floors climbed data for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today'
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        stats = client.get_stats(date_str)
        if stats:
            return {
                "date": date_str,
                "floors_climbed": stats.get("floorsAscended", 0),
                "floors_descended": stats.get("floorsDescended", 0),
                "floors_goal": stats.get("floorsAscendedGoal"),
            }
        return {"date": date_str, "error": "No data available"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_all_day_stress(date_str: str = "today") -> dict:
    """
    Get detailed stress data throughout the day with timestamps.

    Args:
        date_str: Date in YYYY-MM-DD format, or 'today'
    """
    client = get_garmin_client()

    if date_str == "today":
        date_str = date.today().isoformat()

    try:
        stress = client.get_stress_data(date_str)
        if stress:
            # Get stress readings
            readings = stress.get("stressValuesArray", [])

            # Categorize readings
            rest = 0
            low = 0
            medium = 0
            high = 0

            for r in readings:
                if len(r) > 1:
                    level = r[1]
                    if level < 0:
                        continue  # Invalid/unmeasured
                    elif level <= 25:
                        rest += 1
                    elif level <= 50:
                        low += 1
                    elif level <= 75:
                        medium += 1
                    else:
                        high += 1

            total = rest + low + medium + high
            interval_minutes = 3  # Garmin typically uses 3-minute intervals

            return {
                "date": date_str,
                "avg_stress": stress.get("avgStressLevel"),
                "max_stress": stress.get("maxStressLevel"),
                "reading_count": len(readings),
                "time_by_level": {
                    "rest_minutes": rest * interval_minutes,
                    "low_minutes": low * interval_minutes,
                    "medium_minutes": medium * interval_minutes,
                    "high_minutes": high * interval_minutes,
                },
                "percentage_by_level": {
                    "rest_pct": round(rest / total * 100, 1) if total else 0,
                    "low_pct": round(low / total * 100, 1) if total else 0,
                    "medium_pct": round(medium / total * 100, 1) if total else 0,
                    "high_pct": round(high / total * 100, 1) if total else 0,
                }
            }
        return {"date": date_str, "error": "No stress data available"}
    except Exception as e:
        return {"date": date_str, "error": str(e)}


@mcp.tool
def get_sleep_quality_trends(days: int = 7) -> dict:
    """
    Get sleep quality trends over multiple days.

    Args:
        days: Number of days to analyze (default 7, max 30)
    """
    client = get_garmin_client()
    days = min(max(1, days), 30)

    date_strs = [(date.today() - timedelta(days=i)).isoformat() for i in range(days)]

    def fetch_sleep(date_str):
        try:
            sleep = client.get_sleep_data(date_str)
            if sleep:
                daily = sleep.get("dailySleepDTO", {})
                if daily.get("sleepTimeSeconds"):
                    return {
                        "date": date_str,
                        "sleep_hours": round(daily.get("sleepTimeSeconds", 0) / 3600, 1),
                        "deep_pct": round(daily.get("deepSleepSeconds", 0) / daily.get("sleepTimeSeconds", 1) * 100, 1),
                        "rem_pct": round(daily.get("remSleepSeconds", 0) / daily.get("sleepTimeSeconds", 1) * 100, 1),
                        "light_pct": round(daily.get("lightSleepSeconds", 0) / daily.get("sleepTimeSeconds", 1) * 100, 1),
                        "awake_count": daily.get("awakeSleepCount") or daily.get("awakeCount"),
                        "sleep_score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
                        "avg_hr": daily.get("averageHeartRate") or daily.get("avgHeartRate"),
                        "avg_stress": daily.get("avgSleepStress"),
                    }
        except Exception as e:
            logger.warning(f"Failed to get sleep quality for {date_str}: {e}")
        return None

    tasks = [(fetch_sleep, d) for d in date_strs]
    raw = _parallel_fetch(tasks)
    results = [r for r in raw if r is not None]

    if not results:
        return {"error": "No sleep data available"}

    # Calculate averages
    sleep_hours = [r["sleep_hours"] for r in results if r.get("sleep_hours")]
    scores = [r["sleep_score"] for r in results if r.get("sleep_score")]
    deep_pct = [r["deep_pct"] for r in results if r.get("deep_pct")]

    return {
        "period": f"Last {days} days",
        "nights_analyzed": len(results),
        "averages": {
            "sleep_hours": round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else None,
            "sleep_score": round(sum(scores) / len(scores)) if scores else None,
            "deep_sleep_pct": round(sum(deep_pct) / len(deep_pct), 1) if deep_pct else None,
        },
        "best_night": max(results, key=lambda x: x.get("sleep_score") or 0) if results else None,
        "worst_night": min(results, key=lambda x: x.get("sleep_score") or 100) if results else None,
        "daily_data": results,
    }


@mcp.tool
def get_recovery_metrics() -> dict:
    """
    Get comprehensive recovery metrics including HRV, sleep, stress, and body battery.
    Useful for determining readiness for training.
    """
    client = get_garmin_client()
    today = date.today().isoformat()

    result = {"date": today}

    # Training readiness
    try:
        readiness_list = client.get_training_readiness(today)
        if readiness_list and isinstance(readiness_list, list) and len(readiness_list) > 0:
            readiness = readiness_list[0]
            result["training_readiness"] = {
                "score": readiness.get("score"),
                "level": readiness.get("level"),
                "recovery_time_hours": readiness.get("recoveryTime"),
            }
    except Exception as e:
        logger.warning(f"Failed to get training readiness: {e}")

    # HRV
    try:
        hrv = client.get_hrv_data(today)
        if hrv:
            summary = hrv.get("hrvSummary", {})
            result["hrv"] = {
                "last_night_avg": summary.get("lastNightAvg"),
                "weekly_avg": summary.get("weeklyAvg"),
                "status": summary.get("status"),
                "baseline_low": summary.get("baseline", {}).get("lowUpper"),
                "baseline_balanced_low": summary.get("baseline", {}).get("balancedLow"),
                "baseline_balanced_high": summary.get("baseline", {}).get("balancedUpper"),
            }
    except Exception as e:
        logger.warning(f"Failed to get HRV data: {e}")

    # Sleep
    try:
        sleep = client.get_sleep_data(today)
        if sleep:
            daily = sleep.get("dailySleepDTO", {})
            result["last_night_sleep"] = {
                "hours": round(daily.get("sleepTimeSeconds", 0) / 3600, 1),
                "score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
                "deep_pct": round(daily.get("deepSleepSeconds", 0) / max(daily.get("sleepTimeSeconds", 1), 1) * 100, 1),
            }
    except Exception as e:
        logger.warning(f"Failed to get sleep data for recovery: {e}")

    # Body battery
    try:
        bb = client.get_body_battery(today)
        if bb and isinstance(bb, list) and len(bb) > 0:
            bb_data = bb[0]
            bb_values = bb_data.get("bodyBatteryValuesArray", [])
            if bb_values:
                levels = [v[1] for v in bb_values if len(v) > 1]
                if levels:
                    result["body_battery"] = {
                        "current": levels[-1],
                        "morning_high": max(levels),
                        "charged_overnight": bb_data.get("charged"),
                    }
    except Exception as e:
        logger.warning(f"Failed to get body battery for recovery: {e}")

    # Stress
    try:
        stress = client.get_stress_data(today)
        if stress:
            result["stress"] = {
                "avg_level": stress.get("avgStressLevel"),
            }
    except Exception as e:
        logger.warning(f"Failed to get stress data for recovery: {e}")

    # Resting HR
    try:
        hr = client.get_heart_rates(today)
        if hr:
            result["resting_heart_rate"] = hr.get("restingHeartRate")
            result["resting_hr_7day_avg"] = hr.get("lastSevenDaysAvgRestingHeartRate")
    except Exception as e:
        logger.warning(f"Failed to get heart rate for recovery: {e}")

    # Overall recommendation
    score = result.get("training_readiness", {}).get("score", 0) or 0
    bb_level = result.get("body_battery", {}).get("current", 0) or 0

    if score >= 70 and bb_level >= 50:
        result["recommendation"] = "Ready for high intensity training"
    elif score >= 50 and bb_level >= 30:
        result["recommendation"] = "Moderate training recommended"
    elif score >= 30 or bb_level >= 20:
        result["recommendation"] = "Light activity or recovery day recommended"
    else:
        result["recommendation"] = "Rest day recommended"

    return result


@mcp.tool
def get_step_streak() -> dict:
    """
    Get information about step goal streaks and consistency.
    """
    client = get_garmin_client()

    try:
        # Look back 60 days
        days_back = 60
        current = date.today()
        streak_count = 0
        best_streak = 0
        days_achieved = 0
        current_streak_active = True

        for i in range(days_back):
            date_str = current.isoformat()

            try:
                stats = client.get_stats(date_str)
                if stats:
                    steps = stats.get("totalSteps", 0)
                    goal = stats.get("dailyStepGoal", 0)

                    if goal and steps >= goal:
                        if current_streak_active:
                            streak_count += 1
                        days_achieved += 1
                        best_streak = max(best_streak, streak_count if current_streak_active else 1)
                    else:
                        current_streak_active = False
            except Exception as e:
                logger.warning(f"Failed to get step streak stats for {date_str}: {e}")
                current_streak_active = False

            current -= timedelta(days=1)

        return {
            "current_streak_days": streak_count,
            "best_streak_days": best_streak,
            "days_achieved_last_60": days_achieved,
            "achievement_rate_pct": round(days_achieved / 60 * 100, 1),
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# COMPREHENSIVE WEEKLY HEALTH REPORT
# =============================================================================

def _fetch_full_day(client: Garmin, date_str: str) -> dict:
    """
    Fetch ALL health metrics for a single date in parallel sub-tasks.
    Returns a rich dict with sleep, HRV, stress, body battery, steps, HR.
    """
    def get_sleep():
        try:
            data = client.get_sleep_data(date_str)
            if data:
                daily = data.get("dailySleepDTO", {})
                sleep_sec = daily.get("sleepTimeSeconds", 0)
                start_ts = daily.get("sleepStartTimestampLocal") or daily.get("sleepStartTimestampGMT")
                end_ts = daily.get("sleepEndTimestampLocal") or daily.get("sleepEndTimestampGMT")
                return {
                    "total_hours": round(sleep_sec / 3600, 2) if sleep_sec else None,
                    "deep_hours": round((daily.get("deepSleepSeconds") or 0) / 3600, 2),
                    "light_hours": round((daily.get("lightSleepSeconds") or 0) / 3600, 2),
                    "rem_hours": round((daily.get("remSleepSeconds") or 0) / 3600, 2),
                    "awake_hours": round((daily.get("awakeSleepSeconds") or 0) / 3600, 2),
                    "awake_count": daily.get("awakeSleepCount") or daily.get("awakeCount"),
                    "score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
                    "avg_heart_rate": daily.get("averageHeartRate") or daily.get("avgHeartRate"),
                    "avg_sleep_stress": daily.get("avgSleepStress"),
                    "start_time": _ts_to_readable(start_ts),
                    "end_time": _ts_to_readable(end_ts),
                }
        except Exception as e:
            logger.warning(f"weekly report: sleep failed for {date_str}: {e}")
        return {}

    def get_hrv():
        try:
            data = client.get_hrv_data(date_str)
            if data:
                s = data.get("hrvSummary", {})
                return {
                    "nightly_avg": s.get("lastNightAvg"),
                    "weekly_avg": s.get("weeklyAvg"),
                    "status": s.get("status"),
                    "feedback": s.get("feedbackPhrase"),
                }
        except Exception as e:
            logger.warning(f"weekly report: HRV failed for {date_str}: {e}")
        return {}

    def get_stress():
        try:
            data = client.get_stress_data(date_str)
            if data:
                return {
                    "avg": data.get("avgStressLevel"),
                    "max": data.get("maxStressLevel"),
                }
        except Exception as e:
            logger.warning(f"weekly report: stress failed for {date_str}: {e}")
        return {}

    def get_bb():
        try:
            bb = client.get_body_battery(date_str)
            if bb and isinstance(bb, list) and len(bb) > 0:
                bb_data = bb[0]
                bb_values = bb_data.get("bodyBatteryValuesArray", [])
                levels = [v[1] for v in bb_values if len(v) > 1] if bb_values else []
                return {
                    "charged": bb_data.get("charged"),
                    "drained": bb_data.get("drained"),
                    "high": max(levels) if levels else None,
                    "low": min(levels) if levels else None,
                    "end_of_day": levels[-1] if levels else None,
                }
        except Exception as e:
            logger.warning(f"weekly report: body battery failed for {date_str}: {e}")
        return {}

    def get_hr():
        try:
            data = client.get_heart_rates(date_str)
            if data:
                return {"resting": data.get("restingHeartRate")}
        except Exception as e:
            logger.warning(f"weekly report: HR failed for {date_str}: {e}")
        return {}

    def get_steps():
        try:
            data = client.get_stats(date_str)
            if data:
                return {
                    "count": data.get("totalSteps", 0),
                    "goal": data.get("dailyStepGoal", 0),
                    "calories": data.get("totalKilocalories", 0),
                    "active_calories": data.get("activeKilocalories", 0),
                }
        except Exception as e:
            logger.warning(f"weekly report: steps failed for {date_str}: {e}")
        return {}

    # Run all sub-fetches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        f_sleep = pool.submit(get_sleep)
        f_hrv = pool.submit(get_hrv)
        f_stress = pool.submit(get_stress)
        f_bb = pool.submit(get_bb)
        f_hr = pool.submit(get_hr)
        f_steps = pool.submit(get_steps)

    return {
        "date": date_str,
        "sleep": f_sleep.result(),
        "hrv": f_hrv.result(),
        "stress": f_stress.result(),
        "body_battery": f_bb.result(),
        "heart_rate": f_hr.result(),
        "steps": f_steps.result(),
    }


def _compute_week_over_week(current_days: list, prior_days: list) -> dict:
    """Compute week-over-week differences and percent changes for key metrics."""
    def avg(days, path):
        vals = []
        for d in days:
            try:
                v = d
                for key in path:
                    v = v.get(key) if isinstance(v, dict) else None
                    if v is None:
                        break
                if v is not None:
                    vals.append(float(v))
            except Exception:
                pass
        return round(sum(vals) / len(vals), 2) if vals else None

    def total(days, path):
        vals = []
        for d in days:
            try:
                v = d
                for key in path:
                    v = v.get(key) if isinstance(v, dict) else None
                    if v is None:
                        break
                if v is not None:
                    vals.append(float(v))
            except Exception:
                pass
        return round(sum(vals), 1) if vals else None

    def diff_pct(cur, pri):
        if cur is None or pri is None or pri == 0:
            return None
        return round((cur - pri) / abs(pri) * 100, 1)

    metrics = {
        "steps_total": (total(current_days, ["steps", "count"]), total(prior_days, ["steps", "count"])),
        "sleep_avg_hours": (avg(current_days, ["sleep", "total_hours"]), avg(prior_days, ["sleep", "total_hours"])),
        "sleep_score_avg": (avg(current_days, ["sleep", "score"]), avg(prior_days, ["sleep", "score"])),
        "hrv_avg": (avg(current_days, ["hrv", "nightly_avg"]), avg(prior_days, ["hrv", "nightly_avg"])),
        "stress_avg": (avg(current_days, ["stress", "avg"]), avg(prior_days, ["stress", "avg"])),
        "resting_hr_avg": (avg(current_days, ["heart_rate", "resting"]), avg(prior_days, ["heart_rate", "resting"])),
        "body_battery_high_avg": (avg(current_days, ["body_battery", "high"]), avg(prior_days, ["body_battery", "high"])),
    }

    result = {}
    for metric, (cur, pri) in metrics.items():
        result[metric] = {
            "current_week": cur,
            "prior_week": pri,
            "diff": round(cur - pri, 2) if cur is not None and pri is not None else None,
            "pct_change": diff_pct(cur, pri),
        }
    return result


@mcp.tool
def get_weekly_health_report(end_date: str = "today") -> dict:
    """
    Comprehensive weekly health report — returns 7 days of all key metrics in ONE call.
    Replaces 80+ sequential API calls by fetching everything in parallel.

    Includes:
    - 7 days of sleep (stages, score, avg HR, awake count, times)
    - 7 days of HRV (nightly avg + status)
    - 7 days of stress (avg/max)
    - 7 days of body battery (high/low/charged/drained)
    - 7 days of resting HR and steps
    - Week-over-week comparison vs prior 7 days
    - Weight/body composition history (last 30 days)
    - Recent strength training activities (last 10) with exercise sets
    - Current training readiness + training status
    - Sleep quality trends
    - Current recovery metrics

    Args:
        end_date: Last date of the report period (YYYY-MM-DD or 'today')
    """
    client = get_garmin_client()

    if end_date == "today":
        end_dt = date.today()
    else:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD or 'today'"}

    # Build date lists
    current_week_dates = [(end_dt - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    prior_week_dates = [(end_dt - timedelta(days=i)).isoformat() for i in range(13, 6, -1)]

    logger.info(f"Weekly health report: fetching {len(current_week_dates) + len(prior_week_dates)} day-sets in parallel")

    # ── Fetch per-day data for both weeks in parallel ──────────────────────────
    all_dates = current_week_dates + prior_week_dates
    tasks = [(_fetch_full_day, client, d) for d in all_dates]
    all_day_results = _parallel_fetch(tasks)

    current_days = all_day_results[:7]
    prior_days = all_day_results[7:]

    # Replace any None results with placeholder dicts
    current_days = [r if r else {"date": current_week_dates[i]} for i, r in enumerate(current_days)]
    prior_days = [r if r else {"date": prior_week_dates[i]} for i, r in enumerate(prior_days)]

    # ── Fetch supporting data in parallel (weight, activities, readiness, etc.) ──
    def fetch_weight():
        try:
            end_str = end_dt.isoformat()
            start_str = (end_dt - timedelta(days=30)).isoformat()
            bc = client.get_body_composition(start_str, end_str)
            if bc:
                weights = bc.get("dateWeightList", [])
                return [
                    {
                        "date": w.get("calendarDate"),
                        "weight_kg": round(w.get("weight", 0) / 1000, 2),
                        "weight_lb": round(w.get("weight", 0) / 1000 * 2.20462, 1),
                        "body_fat_pct": w.get("bodyFat"),
                        "muscle_mass_kg": round(w.get("muscleMass", 0) / 1000, 2) if w.get("muscleMass") else None,
                    }
                    for w in weights if w.get("weight")
                ]
        except Exception as e:
            logger.warning(f"weekly report: weight history failed: {e}")
        return []

    def fetch_strength_activities():
        try:
            activities = client.get_activities(0, 40)
            if not activities:
                return []
            strength = [
                a for a in activities
                if "strength" in (a.get("activityType", {}).get("typeKey") or "").lower()
            ][:10]

            result = []
            for act in strength:
                act_id = act.get("activityId")
                sets_data = {}
                if act_id:
                    try:
                        sets_data = client.get_activity_exercise_sets(act_id) or {}
                        # Parse sets into clean format
                        raw_sets = sets_data.get("exerciseSets", []) if isinstance(sets_data, dict) else []
                        exercises_map: dict = {}
                        for s in raw_sets:
                            category = s.get("exerciseCategory") or s.get("category") or "Unknown"
                            exercise_name = (
                                s.get("exercises", [{}])[0].get("exerciseName")
                                if s.get("exercises")
                                else s.get("exerciseName") or category
                            )
                            key = exercise_name or category
                            if key not in exercises_map:
                                exercises_map[key] = {"name": exercise_name or category, "category": category, "sets": []}
                            set_num = len(exercises_map[key]["sets"]) + 1
                            reps = s.get("repetitionCount") or s.get("reps")
                            weight_g = s.get("weight")
                            weight_kg = round(weight_g / 1000, 2) if weight_g else None
                            exercises_map[key]["sets"].append({
                                "set_number": set_num,
                                "reps": reps,
                                "weight_kg": weight_kg,
                                "weight_lb": round(weight_kg * 2.20462, 1) if weight_kg else None,
                                "duration_seconds": s.get("duration") or s.get("durationInSeconds"),
                            })
                        sets_data = {"exercises": list(exercises_map.values())}
                    except Exception as e:
                        logger.warning(f"weekly report: exercise sets failed for {act_id}: {e}")
                        sets_data = {}

                result.append({
                    "id": act_id,
                    "name": act.get("activityName"),
                    "date": act.get("startTimeLocal"),
                    "duration_minutes": round(act.get("duration", 0) / 60, 1),
                    "calories": act.get("calories"),
                    "avg_hr": act.get("averageHR"),
                    "exercises": sets_data.get("exercises", []),
                })
            return result
        except Exception as e:
            logger.warning(f"weekly report: strength activities failed: {e}")
        return []

    def fetch_training_readiness():
        try:
            today_str = end_dt.isoformat()
            readiness_list = client.get_training_readiness(today_str)
            if readiness_list and isinstance(readiness_list, list) and len(readiness_list) > 0:
                r = readiness_list[0]
                return {
                    "score": r.get("score"),
                    "level": r.get("level"),
                    "feedback": r.get("feedbackShort"),
                    "recovery_time_hours": r.get("recoveryTime"),
                    "sleep_score": r.get("sleepScore"),
                    "hrv_feedback": r.get("hrvFactorFeedback"),
                }
        except Exception as e:
            logger.warning(f"weekly report: training readiness failed: {e}")
        return {}

    def fetch_training_status():
        try:
            today_str = end_dt.isoformat()
            status = client.get_training_status(today_str)
            if status:
                vo2_obj = status.get("mostRecentVO2Max", {}) or {}
                ts_obj = status.get("mostRecentTrainingStatus", {}) or {}
                lb_obj = status.get("mostRecentTrainingLoadBalance", {}) or {}
                return {
                    "training_status": ts_obj.get("trainingStatusLabel") or ts_obj.get("trainingStatusKey"),
                    "vo2_max": vo2_obj.get("vo2MaxValue") or vo2_obj.get("vo2Max"),
                    "weekly_load": lb_obj.get("weeklyLoadTotal"),
                    "acute_load": lb_obj.get("acuteLoad"),
                    "chronic_load": lb_obj.get("chronicLoad"),
                }
        except Exception as e:
            logger.warning(f"weekly report: training status failed: {e}")
        return {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        f_weight = pool.submit(fetch_weight)
        f_strength = pool.submit(fetch_strength_activities)
        f_readiness = pool.submit(fetch_training_readiness)
        f_status = pool.submit(fetch_training_status)

    weight_history = f_weight.result()
    strength_activities = f_strength.result()
    training_readiness = f_readiness.result()
    training_status = f_status.result()

    # ── Week-over-week comparison ──────────────────────────────────────────────
    wow = _compute_week_over_week(current_days, prior_days)

    # ── Sleep quality trends (just the 7 current days) ────────────────────────
    sleep_trends = []
    for d in current_days:
        s = d.get("sleep", {})
        if s.get("total_hours"):
            total_sec = s["total_hours"] * 3600
            sleep_trends.append({
                "date": d["date"],
                "total_hours": s.get("total_hours"),
                "score": s.get("score"),
                "deep_pct": round(s.get("deep_hours", 0) / s["total_hours"] * 100, 1) if s.get("total_hours") else None,
                "rem_pct": round(s.get("rem_hours", 0) / s["total_hours"] * 100, 1) if s.get("total_hours") else None,
                "awake_count": s.get("awake_count"),
                "avg_hr": s.get("avg_heart_rate"),
                "avg_stress": s.get("avg_sleep_stress"),
            })

    # ── Current recovery snapshot (last day in current week) ──────────────────
    last_day = current_days[-1]
    bb_today = last_day.get("body_battery", {})
    hrv_today = last_day.get("hrv", {})
    sleep_today = last_day.get("sleep", {})
    readiness_score = training_readiness.get("score") or 0
    bb_current = bb_today.get("end_of_day") or bb_today.get("high") or 0
    recovery_status = (
        "Ready for high intensity" if readiness_score >= 70 and bb_current >= 50
        else "Moderate training OK" if readiness_score >= 50 and bb_current >= 30
        else "Light activity/recovery day" if readiness_score >= 30 or bb_current >= 20
        else "Rest day recommended"
    )

    return {
        "report_period": {
            "start": current_week_dates[0],
            "end": current_week_dates[-1],
        },
        "daily_data": current_days,
        "week_over_week": wow,
        "sleep_quality_trends": sleep_trends,
        "weight_history_30d": weight_history,
        "strength_activities": strength_activities,
        "training_readiness": training_readiness,
        "training_status": training_status,
        "recovery_snapshot": {
            "date": last_day.get("date"),
            "body_battery_current": bb_current,
            "hrv_last_night": hrv_today.get("nightly_avg"),
            "hrv_status": hrv_today.get("status"),
            "sleep_score": sleep_today.get("score"),
            "readiness_score": readiness_score,
            "recommendation": recovery_status,
        },
    }


if __name__ == "__main__":
    mcp.run()
