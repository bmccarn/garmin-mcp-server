#!/usr/bin/env python3
"""
Debug script to inspect raw Garmin API responses.
Use this to understand the data structure and troubleshoot missing fields.
"""

import json
from datetime import date
from pathlib import Path

from garminconnect import Garmin

TOKEN_DIR = Path.home() / ".garminconnect"


def pretty_print(name, data):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print('='*60)
    print(json.dumps(data, indent=2, default=str))


def main():
    # Load client
    print("Loading Garmin client...")
    client = Garmin()
    client.login(str(TOKEN_DIR))
    print("Authenticated successfully!")

    today = date.today().isoformat()
    print(f"\nFetching data for: {today}")

    # Test each API endpoint
    print("\n" + "#"*60)
    print("# RAW API RESPONSES")
    print("#"*60)

    # Stress data - often returns different structure
    try:
        stress = client.get_stress_data(today)
        pretty_print("STRESS DATA (get_stress_data)", stress)
    except Exception as e:
        print(f"\nSTRESS DATA ERROR: {e}")

    # Body battery
    try:
        bb = client.get_body_battery(today)
        pretty_print("BODY BATTERY (get_body_battery)", bb)
        if bb and isinstance(bb, list):
            print(f"\n  -> Found {len(bb)} readings")
            if bb:
                print(f"  -> Sample reading keys: {list(bb[0].keys()) if bb else 'N/A'}")
    except Exception as e:
        print(f"\nBODY BATTERY ERROR: {e}")

    # Daily stats
    try:
        stats = client.get_stats(today)
        pretty_print("DAILY STATS (get_stats) - First 20 keys",
                    {k: stats.get(k) for k in list(stats.keys())[:20]} if stats else None)
    except Exception as e:
        print(f"\nDAILY STATS ERROR: {e}")

    # Heart rate
    try:
        hr = client.get_heart_rates(today)
        # Show summary without the detailed readings
        if hr:
            hr_summary = {k: v for k, v in hr.items() if k != 'heartRateValues'}
            hr_summary['heartRateValues_count'] = len(hr.get('heartRateValues', []))
            pretty_print("HEART RATE (get_heart_rates) - Summary", hr_summary)
    except Exception as e:
        print(f"\nHEART RATE ERROR: {e}")

    # Sleep
    try:
        sleep = client.get_sleep_data(today)
        if sleep:
            daily = sleep.get('dailySleepDTO', {})
            pretty_print("SLEEP (get_sleep_data) - dailySleepDTO", daily)
    except Exception as e:
        print(f"\nSLEEP ERROR: {e}")

    # HRV
    try:
        hrv = client.get_hrv_data(today)
        pretty_print("HRV (get_hrv_data)", hrv)
    except Exception as e:
        print(f"\nHRV ERROR: {e}")

    # SpO2
    try:
        spo2 = client.get_spo2_data(today)
        pretty_print("SPO2 (get_spo2_data)", spo2)
    except Exception as e:
        print(f"\nSPO2 ERROR: {e}")

    # Respiration
    try:
        resp = client.get_respiration_data(today)
        pretty_print("RESPIRATION (get_respiration_data)", resp)
    except Exception as e:
        print(f"\nRESPIRATION ERROR: {e}")

    print("\n" + "#"*60)
    print("# DEBUG COMPLETE")
    print("#"*60)
    print("\nUse the output above to understand the API response structure.")
    print("If fields are missing, the API may have changed or your device")
    print("may not track that specific metric.")


if __name__ == "__main__":
    main()
