#!/usr/bin/env python3
"""
Garmin Connect MCP Server
Exposes Garmin health and fitness data to AI models via Model Context Protocol
"""

import os
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastmcp import FastMCP, Context
from garminconnect import Garmin, GarminConnectAuthenticationError

# Token storage directory
TOKEN_DIR = Path.home() / ".garminconnect"

# Global client instance
_garmin_client: Optional[Garmin] = None


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
    When asked about trends or comparisons, use the date range tools to get multiple days of data."""
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
            summary["distance_km"] = round(stats.get("totalDistanceMeters", 0) / 1000, 2)
            summary["active_calories"] = stats.get("activeKilocalories", 0)
            summary["total_calories"] = stats.get("totalKilocalories", 0)
            summary["floors_climbed"] = stats.get("floorsAscended", 0)
            summary["intensity_minutes"] = stats.get("intensityMinutes", 0)
    except Exception:
        pass

    # Heart rate
    try:
        hr = client.get_heart_rates(today)
        if hr:
            summary["resting_heart_rate"] = hr.get("restingHeartRate")
            summary["min_heart_rate"] = hr.get("minHeartRate")
            summary["max_heart_rate"] = hr.get("maxHeartRate")
    except Exception:
        pass

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
    except Exception:
        pass

    # Stress
    try:
        stress = client.get_stress_data(today)
        if stress:
            summary["stress_avg"] = stress.get("avgStressLevel")
            summary["stress_max"] = stress.get("maxStressLevel")
    except Exception:
        pass

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
    except Exception:
        pass

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
            return {
                "date": date_str,
                "steps": stats.get("totalSteps", 0),
                "step_goal": stats.get("dailyStepGoal", 0),
                "distance_meters": stats.get("totalDistanceMeters", 0),
                "distance_km": round(stats.get("totalDistanceMeters", 0) / 1000, 2),
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
    Get sleep data for a specific date including duration, stages, and sleep score.

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

            return {
                "date": date_str,
                "sleep_start": daily.get("sleepStartTimestampLocal"),
                "sleep_end": daily.get("sleepEndTimestampLocal"),
                "total_sleep_hours": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
                "deep_sleep_hours": round(daily.get("deepSleepSeconds", 0) / 3600, 2),
                "light_sleep_hours": round(daily.get("lightSleepSeconds", 0) / 3600, 2),
                "rem_sleep_hours": round(daily.get("remSleepSeconds", 0) / 3600, 2),
                "awake_hours": round(daily.get("awakeSleepSeconds", 0) / 3600, 2),
                "sleep_score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
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
                act = {
                    "name": activity.get("activityName"),
                    "type": activity.get("activityType", {}).get("typeKey"),
                    "date": activity.get("startTimeLocal"),
                    "duration_minutes": round(activity.get("duration", 0) / 60, 1),
                    "distance_km": round(activity.get("distance", 0) / 1000, 2),
                    "calories": activity.get("calories"),
                    "avg_heart_rate": activity.get("averageHR"),
                    "max_heart_rate": activity.get("maxHR"),
                }

                # Calculate pace for running/walking activities
                avg_speed = activity.get("averageSpeed")
                if avg_speed and avg_speed > 0:
                    pace_min_per_km = 1000 / (avg_speed * 60)
                    act["avg_pace_per_km"] = f"{int(pace_min_per_km)}:{int((pace_min_per_km % 1) * 60):02d}"

                result.append(act)
            return result
        return []
    except Exception as e:
        return [{"error": str(e)}]


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
            return {
                "training_status": status.get("trainingStatusLabel"),
                "vo2_max": status.get("vo2MaxValue"),
                "weekly_load": status.get("weeklyLoadTotal"),
                "acute_load": status.get("acuteLoad"),
                "chronic_load": status.get("chronicLoad"),
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
        readiness = client.get_training_readiness(today)
        if readiness:
            return {
                "score": readiness.get("score"),
                "level": readiness.get("level"),
                "recovery_time_hours": readiness.get("recoveryTimeHours"),
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
    start = (date.today() - timedelta(days=30)).isoformat()

    try:
        bc = client.get_body_composition(start, today)
        if bc:
            weight_g = bc.get("weight", 0)
            weight_kg = weight_g / 1000 if weight_g else None
            weight_lb = weight_kg * 2.20462 if weight_kg else None

            return {
                "weight_kg": round(weight_kg, 1) if weight_kg else None,
                "weight_lb": round(weight_lb, 1) if weight_lb else None,
                "bmi": bc.get("bmi"),
                "body_fat_percent": bc.get("bodyFat"),
                "body_water_percent": bc.get("bodyWater"),
                "bone_mass_kg": bc.get("boneMass"),
                "muscle_mass_kg": bc.get("muscleMass"),
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
            return [
                {
                    "type": record.get("typeKey"),
                    "value": record.get("value"),
                    "date": record.get("prStartTimeLocal"),
                }
                for record in records[:20]
            ]
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


@mcp.tool
def get_health_data_for_date_range(
    start_date: str,
    end_date: str,
    metrics: list[str] = ["steps", "sleep", "stress", "heart_rate"]
) -> list:
    """
    Get health data for a date range. Useful for analyzing trends.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        metrics: List of metrics to include. Options: steps, sleep, stress, heart_rate, body_battery, hrv
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

    results = []
    current = start

    while current <= end:
        date_str = current.isoformat()
        day_data = {"date": date_str}

        if "steps" in metrics:
            try:
                stats = client.get_stats(date_str)
                if stats:
                    day_data["steps"] = stats.get("totalSteps", 0)
                    day_data["distance_km"] = round(stats.get("totalDistanceMeters", 0) / 1000, 2)
                    day_data["calories"] = stats.get("totalKilocalories", 0)
            except Exception:
                pass

        if "heart_rate" in metrics:
            try:
                hr = client.get_heart_rates(date_str)
                if hr:
                    day_data["resting_hr"] = hr.get("restingHeartRate")
            except Exception:
                pass

        if "sleep" in metrics:
            try:
                sleep_data = client.get_sleep_data(date_str)
                if sleep_data:
                    daily = sleep_data.get("dailySleepDTO", {})
                    sleep_sec = daily.get("sleepTimeSeconds", 0)
                    day_data["sleep_hours"] = round(sleep_sec / 3600, 1) if sleep_sec else None
                    day_data["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
            except Exception:
                pass

        if "stress" in metrics:
            try:
                stress = client.get_stress_data(date_str)
                if stress:
                    day_data["stress_avg"] = stress.get("avgStressLevel")
                    day_data["stress_max"] = stress.get("maxStressLevel")
            except Exception:
                pass

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
            except Exception:
                pass

        if "hrv" in metrics:
            try:
                hrv = client.get_hrv_data(date_str)
                if hrv:
                    day_data["hrv"] = hrv.get("hrvSummary", {}).get("lastNightAvg")
            except Exception:
                pass

        results.append(day_data)
        current += timedelta(days=1)

    return results


@mcp.tool
def get_weekly_summary() -> dict:
    """
    Get a summary of health metrics for the past 7 days with averages and totals.
    """
    client = get_garmin_client()
    end = date.today()
    start = end - timedelta(days=6)

    data = []
    current = start

    while current <= end:
        date_str = current.isoformat()
        day = {"date": date_str}

        try:
            stats = client.get_stats(date_str)
            if stats:
                day["steps"] = stats.get("totalSteps", 0)
        except Exception:
            day["steps"] = 0

        try:
            hr = client.get_heart_rates(date_str)
            if hr:
                day["resting_hr"] = hr.get("restingHeartRate")
        except Exception:
            pass

        try:
            sleep_data = client.get_sleep_data(date_str)
            if sleep_data:
                daily = sleep_data.get("dailySleepDTO", {})
                sleep_sec = daily.get("sleepTimeSeconds", 0)
                day["sleep_hours"] = round(sleep_sec / 3600, 1) if sleep_sec else None
        except Exception:
            pass

        data.append(day)
        current += timedelta(days=1)

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


if __name__ == "__main__":
    mcp.run()
