#!/usr/bin/env python3
"""
Garmin Connect Health & Fitness App
Retrieves your Garmin stats and health information using python-garminconnect
"""

import os
import sys
import json
import csv
from datetime import date, datetime, timedelta
from getpass import getpass
from pathlib import Path
from time import sleep

from garminconnect import Garmin, GarminConnectAuthenticationError

# Token storage directory
TOKEN_DIR = Path.home() / ".garminconnect"


def get_credentials():
    """Get Garmin Connect credentials from environment or user input."""
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email:
        email = input("Enter your Garmin email: ")
    if not password:
        password = getpass("Enter your Garmin password: ")

    return email, password


def prompt_for_mfa():
    """Prompt user for MFA code when two-factor authentication is required."""
    print("\n*** Two-Factor Authentication Required ***")
    print("A verification code has been sent to your phone via SMS.")
    mfa_code = input("Enter the MFA code: ").strip()
    return mfa_code


def init_client():
    """Initialize and authenticate the Garmin client."""
    print("\n--- Garmin Connect Authentication ---")

    # Check for existing tokens
    token_file = TOKEN_DIR / "oauth1_token.json"

    if token_file.exists():
        print("Found existing session tokens, attempting to resume...")
        try:
            client = Garmin()
            client.login(str(TOKEN_DIR))
            print("Successfully resumed session!")
            return client
        except Exception as e:
            print(f"Could not resume session: {e}")
            print("Will need fresh login...")

    # Fresh login
    email, password = get_credentials()

    try:
        # Create client with MFA prompt callback
        client = Garmin(email, password, prompt_mfa=prompt_for_mfa)
        client.login()
        # Save tokens for future use
        client.garth.dump(TOKEN_DIR)
        print("Login successful! Tokens saved for future sessions.")
        return client
    except GarminConnectAuthenticationError as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)


def format_duration(seconds):
    """Format seconds into readable duration."""
    if not seconds:
        return "N/A"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_distance(meters):
    """Format meters into readable distance."""
    if not meters:
        return "N/A"
    km = meters / 1000
    miles = km * 0.621371
    return f"{km:.2f} km ({miles:.2f} mi)"


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def get_user_profile(client):
    """Display user profile information."""
    print_section("User Profile")
    try:
        profile = client.get_full_name()
        print(f"Name: {profile}")

        user_info = client.get_user_profile()
        if user_info:
            print(f"Display Name: {user_info.get('displayName', 'N/A')}")
            print(f"Profile Image: {'Available' if user_info.get('profileImageUrlLarge') else 'Not set'}")
    except Exception as e:
        print(f"Error getting profile: {e}")


def get_daily_stats(client, date_str):
    """Get daily summary stats."""
    print_section(f"Daily Stats ({date_str})")
    try:
        stats = client.get_stats(date_str)
        if stats:
            print(f"Total Steps: {stats.get('totalSteps', 0):,}")
            print(f"Step Goal: {stats.get('dailyStepGoal', 0):,}")
            print(f"Total Distance: {format_distance(stats.get('totalDistanceMeters'))}")
            print(f"Active Calories: {stats.get('activeKilocalories', 0):,} kcal")
            print(f"Total Calories: {stats.get('totalKilocalories', 0):,} kcal")
            print(f"Floors Climbed: {stats.get('floorsAscended', 0)}")
            print(f"Floors Descended: {stats.get('floorsDescended', 0)}")
            print(f"Intensity Minutes: {stats.get('intensityMinutes', 0)}")
            print(f"Moderate Intensity: {stats.get('moderateIntensityMinutes', 0)} min")
            print(f"Vigorous Intensity: {stats.get('vigorousIntensityMinutes', 0)} min")
        else:
            print("No stats available for this date.")
    except Exception as e:
        print(f"Error getting daily stats: {e}")


def get_heart_rate(client, date_str):
    """Get heart rate data."""
    print_section(f"Heart Rate Data ({date_str})")
    try:
        hr_data = client.get_heart_rates(date_str)
        if hr_data:
            print(f"Resting Heart Rate: {hr_data.get('restingHeartRate', 'N/A')} bpm")
            print(f"Min Heart Rate: {hr_data.get('minHeartRate', 'N/A')} bpm")
            print(f"Max Heart Rate: {hr_data.get('maxHeartRate', 'N/A')} bpm")

            # Heart rate zones
            zones = hr_data.get('heartRateTimeInZones', [])
            if zones:
                print("\nTime in Heart Rate Zones:")
                for zone in zones:
                    zone_name = zone.get('zoneName', 'Unknown')
                    seconds = zone.get('secsInZone', 0)
                    print(f"  {zone_name}: {format_duration(seconds)}")
        else:
            print("No heart rate data available.")
    except Exception as e:
        print(f"Error getting heart rate data: {e}")


def get_sleep_data(client, date_str):
    """Get sleep data."""
    print_section(f"Sleep Data ({date_str})")
    try:
        sleep = client.get_sleep_data(date_str)
        if sleep:
            daily_sleep = sleep.get('dailySleepDTO', {})
            print(f"Sleep Start: {daily_sleep.get('sleepStartTimestampLocal', 'N/A')}")
            print(f"Sleep End: {daily_sleep.get('sleepEndTimestampLocal', 'N/A')}")
            print(f"Total Sleep: {format_duration(daily_sleep.get('sleepTimeSeconds'))}")
            print(f"Deep Sleep: {format_duration(daily_sleep.get('deepSleepSeconds'))}")
            print(f"Light Sleep: {format_duration(daily_sleep.get('lightSleepSeconds'))}")
            print(f"REM Sleep: {format_duration(daily_sleep.get('remSleepSeconds'))}")
            print(f"Awake Time: {format_duration(daily_sleep.get('awakeSleepSeconds'))}")
            print(f"Sleep Score: {daily_sleep.get('sleepScores', {}).get('overall', {}).get('value', 'N/A')}")
        else:
            print("No sleep data available.")
    except Exception as e:
        print(f"Error getting sleep data: {e}")


def get_stress_data(client, date_str):
    """Get stress data."""
    print_section(f"Stress Data ({date_str})")
    try:
        stress = client.get_stress_data(date_str)
        if stress:
            print(f"Overall Stress Level: {stress.get('overallStressLevel', 'N/A')}")
            print(f"Rest Stress Duration: {format_duration(stress.get('restStressDuration'))}")
            print(f"Low Stress Duration: {format_duration(stress.get('lowStressDuration'))}")
            print(f"Medium Stress Duration: {format_duration(stress.get('mediumStressDuration'))}")
            print(f"High Stress Duration: {format_duration(stress.get('highStressDuration'))}")
            print(f"Stress Qualifier: {stress.get('stressQualifier', 'N/A')}")
        else:
            print("No stress data available.")
    except Exception as e:
        print(f"Error getting stress data: {e}")


def get_body_battery(client, date_str):
    """Get body battery data."""
    print_section(f"Body Battery ({date_str})")
    try:
        bb = client.get_body_battery(date_str)
        if bb:
            # Body battery returns a list of readings
            if isinstance(bb, list) and len(bb) > 0:
                latest = bb[-1] if bb else {}
                print(f"Latest Body Battery: {latest.get('bodyBatteryLevel', 'N/A')}")
                print(f"Charged Value: {latest.get('bodyBatteryChargedValue', 'N/A')}")
                print(f"Drained Value: {latest.get('bodyBatteryDrainedValue', 'N/A')}")
            elif isinstance(bb, dict):
                print(f"Body Battery: {bb}")
        else:
            print("No body battery data available.")
    except Exception as e:
        print(f"Error getting body battery: {e}")


def get_respiration(client, date_str):
    """Get respiration data."""
    print_section(f"Respiration Data ({date_str})")
    try:
        resp = client.get_respiration_data(date_str)
        if resp:
            print(f"Avg Waking Respiration: {resp.get('avgWakingRespirationValue', 'N/A')} breaths/min")
            print(f"Highest Respiration: {resp.get('highestRespirationValue', 'N/A')} breaths/min")
            print(f"Lowest Respiration: {resp.get('lowestRespirationValue', 'N/A')} breaths/min")
            print(f"Avg Sleep Respiration: {resp.get('avgSleepRespirationValue', 'N/A')} breaths/min")
        else:
            print("No respiration data available.")
    except Exception as e:
        print(f"Error getting respiration data: {e}")


def get_spo2(client, date_str):
    """Get SpO2 data."""
    print_section(f"SpO2 (Blood Oxygen) Data ({date_str})")
    try:
        spo2 = client.get_spo2_data(date_str)
        if spo2:
            print(f"Average SpO2: {spo2.get('averageSpO2', 'N/A')}%")
            print(f"Lowest SpO2: {spo2.get('lowestSpO2', 'N/A')}%")
            print(f"Latest SpO2: {spo2.get('latestSpO2', 'N/A')}%")
        else:
            print("No SpO2 data available.")
    except Exception as e:
        print(f"Error getting SpO2 data: {e}")


def get_hrv(client, date_str):
    """Get HRV (Heart Rate Variability) data."""
    print_section(f"HRV Data ({date_str})")
    try:
        hrv = client.get_hrv_data(date_str)
        if hrv:
            summary = hrv.get('hrvSummary', {})
            print(f"Weekly Average: {summary.get('weeklyAvg', 'N/A')} ms")
            print(f"Last Night Average: {summary.get('lastNightAvg', 'N/A')} ms")
            print(f"Last Night 5-min High: {summary.get('lastNight5MinHigh', 'N/A')} ms")
            print(f"Status: {summary.get('status', 'N/A')}")
            print(f"Feedback Phrase: {summary.get('feedbackPhrase', 'N/A')}")
        else:
            print("No HRV data available.")
    except Exception as e:
        print(f"Error getting HRV data: {e}")


def get_hydration(client, date_str):
    """Get hydration data."""
    print_section(f"Hydration Data ({date_str})")
    try:
        hydration = client.get_hydration_data(date_str)
        if hydration:
            print(f"Goal: {hydration.get('goalInML', 0)} ml")
            print(f"Intake: {hydration.get('valueInML', 0)} ml")
            print(f"Sweat Loss: {hydration.get('sweatLossInML', 0)} ml")
        else:
            print("No hydration data available.")
    except Exception as e:
        print(f"Error getting hydration data: {e}")


def get_body_composition(client):
    """Get body composition data."""
    print_section("Body Composition (Latest)")
    try:
        today = date.today().isoformat()
        start = (date.today() - timedelta(days=30)).isoformat()
        bc = client.get_body_composition(start, today)
        if bc:
            weight = bc.get('weight', 0)
            if weight:
                weight_kg = weight / 1000
                weight_lb = weight_kg * 2.20462
                print(f"Weight: {weight_kg:.1f} kg ({weight_lb:.1f} lb)")
            print(f"BMI: {bc.get('bmi', 'N/A')}")
            print(f"Body Fat %: {bc.get('bodyFat', 'N/A')}%")
            print(f"Body Water %: {bc.get('bodyWater', 'N/A')}%")
            print(f"Bone Mass: {bc.get('boneMass', 'N/A')} kg")
            print(f"Muscle Mass: {bc.get('muscleMass', 'N/A')} kg")
        else:
            print("No body composition data available.")
    except Exception as e:
        print(f"Error getting body composition: {e}")


def get_activities(client, limit=10):
    """Get recent activities."""
    print_section(f"Recent Activities (Last {limit})")
    try:
        activities = client.get_activities(0, limit)
        if activities:
            for i, activity in enumerate(activities, 1):
                print(f"\n--- Activity {i} ---")
                print(f"Name: {activity.get('activityName', 'N/A')}")
                print(f"Type: {activity.get('activityType', {}).get('typeKey', 'N/A')}")
                print(f"Date: {activity.get('startTimeLocal', 'N/A')}")
                print(f"Duration: {format_duration(activity.get('duration'))}")
                print(f"Distance: {format_distance(activity.get('distance'))}")
                print(f"Calories: {activity.get('calories', 0)} kcal")
                print(f"Avg HR: {activity.get('averageHR', 'N/A')} bpm")
                print(f"Max HR: {activity.get('maxHR', 'N/A')} bpm")

                # For running activities
                avg_speed = activity.get('averageSpeed')
                if avg_speed and avg_speed > 0:
                    pace_min_per_km = 1000 / (avg_speed * 60)
                    pace_min = int(pace_min_per_km)
                    pace_sec = int((pace_min_per_km - pace_min) * 60)
                    print(f"Avg Pace: {pace_min}:{pace_sec:02d} /km")
        else:
            print("No activities found.")
    except Exception as e:
        print(f"Error getting activities: {e}")


def get_training_status(client):
    """Get training status."""
    print_section("Training Status")
    try:
        status = client.get_training_status(date.today().isoformat())
        if status:
            print(f"Training Status: {status.get('trainingStatusLabel', 'N/A')}")
            print(f"VO2 Max: {status.get('vo2MaxValue', 'N/A')}")
            print(f"Training Load: {status.get('weeklyLoadTotal', 'N/A')}")
            print(f"Acute Load: {status.get('acuteLoad', 'N/A')}")
            print(f"Chronic Load: {status.get('chronicLoad', 'N/A')}")
        else:
            print("No training status available.")
    except Exception as e:
        print(f"Error getting training status: {e}")


def get_training_readiness(client):
    """Get training readiness."""
    print_section("Training Readiness")
    try:
        readiness = client.get_training_readiness(date.today().isoformat())
        if readiness:
            print(f"Score: {readiness.get('score', 'N/A')}")
            print(f"Level: {readiness.get('level', 'N/A')}")
            print(f"Recovery Time: {readiness.get('recoveryTimeHours', 'N/A')} hours")
        else:
            print("No training readiness data available.")
    except Exception as e:
        print(f"Error getting training readiness: {e}")


def get_personal_records(client):
    """Get personal records."""
    print_section("Personal Records")
    try:
        records = client.get_personal_record()
        if records:
            for record in records[:10]:  # Show top 10
                print(f"\n{record.get('typeKey', 'Unknown')}:")
                print(f"  Value: {record.get('value', 'N/A')}")
                print(f"  Date: {record.get('prStartTimeLocal', 'N/A')}")
        else:
            print("No personal records found.")
    except Exception as e:
        print(f"Error getting personal records: {e}")


def get_devices(client):
    """Get connected devices."""
    print_section("Connected Devices")
    try:
        devices = client.get_devices()
        if devices:
            for device in devices:
                print(f"\n{device.get('productDisplayName', 'Unknown Device')}")
                print(f"  Unit ID: {device.get('unitId', 'N/A')}")
                print(f"  Software Version: {device.get('softwareVersion', 'N/A')}")
                print(f"  Last Synced: {device.get('lastSyncTime', 'N/A')}")
        else:
            print("No devices found.")
    except Exception as e:
        print(f"Error getting devices: {e}")


def show_daily_summary(client, date_str):
    """Show a complete daily health summary."""
    print(f"\n{'#'*60}")
    print(f"#  DAILY HEALTH SUMMARY - {date_str}")
    print('#'*60)

    get_daily_stats(client, date_str)
    get_heart_rate(client, date_str)
    get_sleep_data(client, date_str)
    get_stress_data(client, date_str)
    get_body_battery(client, date_str)


def interactive_menu(client):
    """Display interactive menu for data retrieval."""
    today = date.today().isoformat()

    while True:
        print(f"\n{'='*50}")
        print("  GARMIN CONNECT - MAIN MENU")
        print('='*50)
        print("\n[Daily Health]")
        print("  1. Today's Summary (Stats, HR, Sleep, Stress, Body Battery)")
        print("  2. Daily Stats")
        print("  3. Heart Rate Data")
        print("  4. Sleep Data")
        print("  5. Stress Data")
        print("  6. Body Battery")
        print("\n[Advanced Health]")
        print("  7. Respiration Data")
        print("  8. SpO2 (Blood Oxygen)")
        print("  9. HRV (Heart Rate Variability)")
        print("  10. Hydration")
        print("  11. Body Composition")
        print("\n[Activities & Training]")
        print("  12. Recent Activities")
        print("  13. Training Status")
        print("  14. Training Readiness")
        print("  15. Personal Records")
        print("\n[Profile & Devices]")
        print("  16. User Profile")
        print("  17. Connected Devices")
        print("\n[Reports & Export]")
        print("  18. View Different Date")
        print("  19. Export Today's Data to JSON")
        print("  20. Generate Date Range Report (CSV/JSON)")
        print("\n  0. Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "0":
            print("\nGoodbye!")
            break
        elif choice == "1":
            show_daily_summary(client, today)
        elif choice == "2":
            get_daily_stats(client, today)
        elif choice == "3":
            get_heart_rate(client, today)
        elif choice == "4":
            get_sleep_data(client, today)
        elif choice == "5":
            get_stress_data(client, today)
        elif choice == "6":
            get_body_battery(client, today)
        elif choice == "7":
            get_respiration(client, today)
        elif choice == "8":
            get_spo2(client, today)
        elif choice == "9":
            get_hrv(client, today)
        elif choice == "10":
            get_hydration(client, today)
        elif choice == "11":
            get_body_composition(client)
        elif choice == "12":
            try:
                limit = int(input("How many activities to show? [10]: ") or "10")
            except ValueError:
                limit = 10
            get_activities(client, limit)
        elif choice == "13":
            get_training_status(client)
        elif choice == "14":
            get_training_readiness(client)
        elif choice == "15":
            get_personal_records(client)
        elif choice == "16":
            get_user_profile(client)
        elif choice == "17":
            get_devices(client)
        elif choice == "18":
            custom_date = input("Enter date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(custom_date, "%Y-%m-%d")
                show_daily_summary(client, custom_date)
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD.")
        elif choice == "19":
            export_data_to_json(client, today)
        elif choice == "20":
            run_date_range_report(client)
        else:
            print("Invalid option. Please try again.")

        input("\nPress Enter to continue...")


def get_date_range():
    """Get date range from user input."""
    print("\nEnter date range for the report:")
    print("  Preset options:")
    print("    1. Last 7 days")
    print("    2. Last 14 days")
    print("    3. Last 30 days")
    print("    4. Last 90 days")
    print("    5. Last 6 months (180 days)")
    print("    6. Custom date range")

    choice = input("\nSelect option [1-6]: ").strip()

    today = date.today()

    if choice == "1":
        start_date = today - timedelta(days=7)
        end_date = today
    elif choice == "2":
        start_date = today - timedelta(days=14)
        end_date = today
    elif choice == "3":
        start_date = today - timedelta(days=30)
        end_date = today
    elif choice == "4":
        start_date = today - timedelta(days=90)
        end_date = today
    elif choice == "5":
        start_date = today - timedelta(days=180)
        end_date = today
    elif choice == "6":
        try:
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid date format.")
            return None, None
    else:
        print("Invalid option, using last 7 days.")
        start_date = today - timedelta(days=7)
        end_date = today

    return start_date, end_date


def collect_daily_data(client, date_str):
    """Collect all daily health metrics for a single day."""
    day_data = {"date": date_str}

    # Daily stats
    try:
        stats = client.get_stats(date_str)
        if stats:
            day_data["steps"] = stats.get("totalSteps", 0)
            day_data["distance_meters"] = stats.get("totalDistanceMeters", 0)
            day_data["active_calories"] = stats.get("activeKilocalories", 0)
            day_data["total_calories"] = stats.get("totalKilocalories", 0)
            day_data["floors_climbed"] = stats.get("floorsAscended", 0)
            day_data["intensity_minutes"] = stats.get("intensityMinutes", 0)
            day_data["moderate_intensity_min"] = stats.get("moderateIntensityMinutes", 0)
            day_data["vigorous_intensity_min"] = stats.get("vigorousIntensityMinutes", 0)
    except Exception:
        pass

    # Heart rate
    try:
        hr = client.get_heart_rates(date_str)
        if hr:
            day_data["resting_hr"] = hr.get("restingHeartRate")
            day_data["min_hr"] = hr.get("minHeartRate")
            day_data["max_hr"] = hr.get("maxHeartRate")
    except Exception:
        pass

    # Sleep
    try:
        sleep_data = client.get_sleep_data(date_str)
        if sleep_data:
            daily = sleep_data.get("dailySleepDTO", {})
            day_data["sleep_seconds"] = daily.get("sleepTimeSeconds")
            day_data["deep_sleep_seconds"] = daily.get("deepSleepSeconds")
            day_data["light_sleep_seconds"] = daily.get("lightSleepSeconds")
            day_data["rem_sleep_seconds"] = daily.get("remSleepSeconds")
            day_data["awake_seconds"] = daily.get("awakeSleepSeconds")
            day_data["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
    except Exception:
        pass

    # Stress
    try:
        stress = client.get_stress_data(date_str)
        if stress:
            day_data["stress_avg"] = stress.get("avgStressLevel")
            day_data["stress_max"] = stress.get("maxStressLevel")
    except Exception:
        pass

    # Body battery
    try:
        bb = client.get_body_battery(date_str)
        if bb and isinstance(bb, list) and len(bb) > 0:
            bb_data = bb[0]  # First element contains the data
            day_data["body_battery_charged"] = bb_data.get("charged")
            day_data["body_battery_drained"] = bb_data.get("drained")
            # Extract levels from bodyBatteryValuesArray
            bb_values = bb_data.get("bodyBatteryValuesArray", [])
            if bb_values:
                levels = [v[1] for v in bb_values if len(v) > 1]
                if levels:
                    day_data["body_battery_high"] = max(levels)
                    day_data["body_battery_low"] = min(levels)
    except Exception:
        pass

    # HRV
    try:
        hrv = client.get_hrv_data(date_str)
        if hrv:
            summary = hrv.get("hrvSummary", {})
            day_data["hrv_weekly_avg"] = summary.get("weeklyAvg")
            day_data["hrv_last_night"] = summary.get("lastNightAvg")
    except Exception:
        pass

    # SpO2
    try:
        spo2 = client.get_spo2_data(date_str)
        if spo2:
            day_data["spo2_avg"] = spo2.get("averageSpO2")
            day_data["spo2_low"] = spo2.get("lowestSpO2")
    except Exception:
        pass

    # Respiration
    try:
        resp = client.get_respiration_data(date_str)
        if resp:
            day_data["respiration_avg"] = resp.get("avgWakingRespirationValue")
            day_data["respiration_sleep_avg"] = resp.get("avgSleepRespirationValue")
    except Exception:
        pass

    return day_data


def generate_date_range_report(client, start_date, end_date):
    """Generate comprehensive report for a date range."""
    print_section(f"Generating Report: {start_date} to {end_date}")

    all_data = []
    current = start_date
    total_days = (end_date - start_date).days + 1

    print(f"Collecting data for {total_days} days...")
    print("(This may take a moment due to API rate limits)\n")

    day_num = 0
    while current <= end_date:
        day_num += 1
        date_str = current.isoformat()
        print(f"  [{day_num}/{total_days}] Fetching {date_str}...", end=" ", flush=True)

        day_data = collect_daily_data(client, date_str)
        all_data.append(day_data)

        print("done")
        current += timedelta(days=1)

        # Small delay to avoid rate limiting
        if day_num < total_days:
            sleep(0.5)

    return all_data


def export_report_to_csv(data, filename):
    """Export report data to CSV file."""
    if not data:
        print("No data to export.")
        return

    # Get all unique keys from all days
    all_keys = set()
    for day in data:
        all_keys.update(day.keys())

    # Sort keys, putting date first
    keys = ["date"] + sorted([k for k in all_keys if k != "date"])

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)

    print(f"CSV exported to: {filename}")


def export_report_to_json(data, filename):
    """Export report data to JSON file."""
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"JSON exported to: {filename}")


def print_report_summary(data):
    """Print a summary of the collected data."""
    if not data:
        print("No data collected.")
        return

    print_section("Report Summary")

    # Calculate averages
    steps = [d.get("steps", 0) for d in data if d.get("steps")]
    resting_hr = [d.get("resting_hr") for d in data if d.get("resting_hr")]
    sleep_hours = [d.get("sleep_seconds", 0) / 3600 for d in data if d.get("sleep_seconds")]
    stress = [d.get("stress_level") for d in data if d.get("stress_level")]
    sleep_scores = [d.get("sleep_score") for d in data if d.get("sleep_score")]

    print(f"Days analyzed: {len(data)}")
    print(f"Date range: {data[0]['date']} to {data[-1]['date']}")

    if steps:
        print(f"\nSteps:")
        print(f"  Average: {sum(steps) / len(steps):,.0f}")
        print(f"  Total: {sum(steps):,}")
        print(f"  Best day: {max(steps):,}")

    if resting_hr:
        print(f"\nResting Heart Rate:")
        print(f"  Average: {sum(resting_hr) / len(resting_hr):.0f} bpm")
        print(f"  Range: {min(resting_hr)} - {max(resting_hr)} bpm")

    if sleep_hours:
        print(f"\nSleep:")
        print(f"  Average: {sum(sleep_hours) / len(sleep_hours):.1f} hours")
        print(f"  Range: {min(sleep_hours):.1f} - {max(sleep_hours):.1f} hours")

    if sleep_scores:
        print(f"\nSleep Score:")
        print(f"  Average: {sum(sleep_scores) / len(sleep_scores):.0f}")
        print(f"  Range: {min(sleep_scores)} - {max(sleep_scores)}")

    if stress:
        print(f"\nStress Level:")
        print(f"  Average: {sum(stress) / len(stress):.0f}")
        print(f"  Range: {min(stress)} - {max(stress)}")


def run_date_range_report(client):
    """Run the date range report workflow."""
    start_date, end_date = get_date_range()

    if start_date is None:
        return

    # Validate range
    if start_date > end_date:
        print("Start date must be before end date.")
        return

    if (end_date - start_date).days > 365:
        print("Warning: Large date range. This may take a while.")
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm != "y":
            return

    # Collect data
    data = generate_date_range_report(client, start_date, end_date)

    # Show summary
    print_report_summary(data)

    # Export options
    print("\n\nExport options:")
    print("  1. Export to CSV")
    print("  2. Export to JSON")
    print("  3. Export to both CSV and JSON")
    print("  4. Skip export")

    export_choice = input("\nSelect option [1-4]: ").strip()

    base_filename = f"garmin_report_{start_date}_{end_date}"

    if export_choice in ["1", "3"]:
        export_report_to_csv(data, f"{base_filename}.csv")
    if export_choice in ["2", "3"]:
        export_report_to_json(data, f"{base_filename}.json")

    if export_choice in ["1", "2", "3"]:
        print(f"\nReport files saved in current directory.")


def export_data_to_json(client, date_str):
    """Export today's data to a JSON file."""
    print_section("Exporting Data to JSON")

    data = {
        "export_date": datetime.now().isoformat(),
        "data_date": date_str,
    }

    try:
        data["stats"] = client.get_stats(date_str)
    except Exception:
        data["stats"] = None

    try:
        data["heart_rate"] = client.get_heart_rates(date_str)
    except Exception:
        data["heart_rate"] = None

    try:
        data["sleep"] = client.get_sleep_data(date_str)
    except Exception:
        data["sleep"] = None

    try:
        data["stress"] = client.get_stress_data(date_str)
    except Exception:
        data["stress"] = None

    try:
        data["body_battery"] = client.get_body_battery(date_str)
    except Exception:
        data["body_battery"] = None

    try:
        data["activities"] = client.get_activities(0, 10)
    except Exception:
        data["activities"] = None

    filename = f"garmin_export_{date_str}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"Data exported to {filename}")


def main():
    """Main entry point."""
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║     GARMIN CONNECT HEALTH & FITNESS APP           ║
    ║     ─────────────────────────────────────────     ║
    ║     Retrieve your health stats and activities    ║
    ╚═══════════════════════════════════════════════════╝
    """)

    # Initialize client
    client = init_client()

    # Run interactive menu
    interactive_menu(client)


if __name__ == "__main__":
    main()
