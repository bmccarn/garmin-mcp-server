"""
Garmin Connect Tools for Open WebUI
Connects to MCPO proxy which bridges to the Garmin MCP SSE server.

To use: Copy this code into Open WebUI Admin Panel -> Workspace -> Tools -> Add Tool (+)

Available tools (30 total):
- Health summaries: get_todays_summary, get_weekly_summary, get_recovery_metrics
- Daily metrics: get_daily_stats, get_heart_rate, get_sleep, get_stress, get_body_battery
- Advanced health: get_hrv, get_spo2, get_respiration, get_hydration
- Body composition: get_body_composition, get_weight_history
- Activities: get_recent_activities, get_activities_by_type, get_activity_details, search_activities
- Training: get_training_status, get_training_readiness
- Goals & progress: get_daily_goals_progress, get_step_streak
- Trends: get_health_data_for_date_range, get_sleep_quality_trends, compare_periods
- Other: get_devices, get_personal_records, get_badges, get_floors_data, get_all_day_stress
"""

import requests
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union


class Tools:
    def __init__(self):
        # MCPO proxy URL - connects to your existing Garmin MCP SSE server
        self.base_url = "http://mcpo:8080/garmin"
        # Use session for connection pooling
        self.session = requests.Session()

    def _call_tool(self, tool_name: str, params: dict = None, timeout: int = 30) -> Union[Dict, str]:
        """Helper method to call MCP tools with consistent error handling."""
        try:
            if params:
                response = self.session.post(
                    f"{self.base_url}/{tool_name}",
                    json=params,
                    timeout=timeout,
                )
            else:
                response = self.session.post(
                    f"{self.base_url}/{tool_name}",
                    timeout=timeout,
                )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": f"Failed to call {tool_name}: {str(e)}"}

    # =========================================================================
    # HEALTH SUMMARIES - Start here for general health questions
    # =========================================================================

    def get_todays_summary(self) -> Dict:
        """
        Get a comprehensive health summary for TODAY. This is the best starting point
        for questions like "How am I doing today?" or "What's my health status?".

        Returns: steps, heart rate, sleep, stress, body battery all in one call.
        Use this FIRST before calling individual metric tools.
        """
        return self._call_tool("get_todays_summary")

    def get_weekly_summary(self) -> Dict:
        """
        Get a summary of the PAST 7 DAYS with averages and totals.

        Use for questions like "How was my week?" or "What's my average steps this week?".
        Returns: total steps, average daily steps, average resting HR, average sleep hours.
        """
        return self._call_tool("get_weekly_summary")

    def get_recovery_metrics(self) -> Dict:
        """
        Get comprehensive RECOVERY and READINESS metrics for training decisions.

        Use for questions like "Should I work out today?" or "Am I recovered enough to train?".
        Returns: training readiness score, HRV status, sleep score, body battery,
        stress level, and a recommendation (high intensity/moderate/light/rest).
        """
        return self._call_tool("get_recovery_metrics")

    # =========================================================================
    # DAILY HEALTH METRICS - For specific metric questions
    # =========================================================================

    def get_daily_stats(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get daily ACTIVITY stats: steps, calories, distance, floors, intensity minutes.

        Use for questions about physical activity on a specific day.
        """
        return self._call_tool("get_daily_stats", {"date_str": date_str})

    def get_heart_rate(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get HEART RATE data: resting HR, min/max HR, and time spent in each HR zone.

        Use for questions about heart rate or cardiovascular health.
        """
        return self._call_tool("get_heart_rate", {"date_str": date_str})

    def get_sleep(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get SLEEP data: total duration, sleep stages (deep/light/REM/awake), sleep score.

        Use for questions about sleep quality or duration on a specific night.
        """
        return self._call_tool("get_sleep", {"date_str": date_str})

    def get_stress(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get STRESS data: average stress level, max stress level for the day.

        Use for questions about stress levels. For detailed breakdown, use get_all_day_stress.
        """
        return self._call_tool("get_stress", {"date_str": date_str})

    def get_body_battery(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get BODY BATTERY (energy level): current level, high/low for the day, charged/drained amounts.

        Use for questions about energy levels or fatigue.
        """
        return self._call_tool("get_body_battery", {"date_str": date_str})

    # =========================================================================
    # ADVANCED HEALTH METRICS
    # =========================================================================

    def get_hrv(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get HRV (Heart Rate Variability) data: last night average, weekly average, status, baseline.

        HRV is a key indicator of recovery and autonomic nervous system health.
        Higher HRV generally indicates better recovery. Use for recovery/readiness questions.
        """
        return self._call_tool("get_hrv", {"date_str": date_str})

    def get_spo2(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get SpO2 (blood oxygen saturation) data: average, lowest, and latest readings.

        Normal SpO2 is 95-100%. Use for questions about blood oxygen or breathing during sleep.
        """
        return self._call_tool("get_spo2", {"date_str": date_str})

    def get_respiration(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get RESPIRATION (breathing rate) data: waking average, sleep average, high/low.

        Normal adult respiration is 12-20 breaths/min. Elevated rates can indicate stress or illness.
        """
        return self._call_tool("get_respiration", {"date_str": date_str})

    def get_hydration(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get HYDRATION data: water intake, goal, progress percentage, sweat loss.

        Use for questions about water intake or hydration status.
        """
        return self._call_tool("get_hydration", {"date_str": date_str})

    # =========================================================================
    # BODY COMPOSITION & WEIGHT
    # =========================================================================

    def get_body_composition(self) -> Dict:
        """
        Get LATEST body composition: weight, BMI, body fat %, muscle mass, bone mass, body water %.

        Use for current weight/body composition questions. For trends, use get_weight_history.
        """
        return self._call_tool("get_body_composition")

    def get_weight_history(
        self,
        days: int = Field(
            30,
            description="Number of days of history (default 30, max 365)",
        ),
    ) -> Dict:
        """
        Get WEIGHT HISTORY with trend analysis over time.

        Returns: all measurements, weight change, min/max/average, body fat trends.
        Use for questions about weight trends, progress, or changes over time.
        """
        return self._call_tool("get_weight_history", {"days": days})

    # =========================================================================
    # ACTIVITIES & WORKOUTS
    # =========================================================================

    def get_recent_activities(
        self,
        limit: int = Field(
            10,
            description="Number of activities to retrieve (default 10, max 100)",
        ),
    ) -> Dict:
        """
        Get list of RECENT ACTIVITIES/WORKOUTS with basic info.

        Returns: name, type, date, duration, distance, calories, heart rate.
        Use as starting point for activity questions, then get_activity_details for specifics.
        """
        return self._call_tool("get_recent_activities", {"limit": limit})

    def get_activities_by_type(
        self,
        activity_type: str = Field(
            ...,
            description="Type: running, cycling, walking, swimming, strength_training, hiking, etc.",
        ),
        limit: int = Field(
            20,
            description="Number of activities to retrieve (max 100)",
        ),
    ) -> Dict:
        """
        Get activities FILTERED BY TYPE (e.g., only running or only cycling).

        Use for questions like "Show me my recent runs" or "How have my cycling workouts been?".
        """
        return self._call_tool("get_activities_by_type", {"activity_type": activity_type, "limit": limit})

    def get_activity_details(
        self,
        activity_id: int = Field(
            ...,
            description="Activity ID (get from get_recent_activities or get_activities_by_type)",
        ),
    ) -> Dict:
        """
        Get DETAILED info about a specific activity including splits, laps, and HR zones.

        Use after getting activity list to dive into specifics of one workout.
        Returns: full stats, lap-by-lap breakdown, time in HR zones, training effect.
        """
        return self._call_tool("get_activity_details", {"activity_id": activity_id})

    def search_activities(
        self,
        query: str = Field(
            "",
            description="Search text in activity name (optional)",
        ),
        start_date: str = Field(
            "",
            description="Filter activities after this date YYYY-MM-DD (optional)",
        ),
        end_date: str = Field(
            "",
            description="Filter activities before this date YYYY-MM-DD (optional)",
        ),
        min_distance_km: float = Field(
            0,
            description="Minimum distance in km (optional)",
        ),
        min_duration_minutes: float = Field(
            0,
            description="Minimum duration in minutes (optional)",
        ),
        limit: int = Field(
            50,
            description="Maximum results (default 50, max 100)",
        ),
    ) -> Dict:
        """
        SEARCH and filter activities with multiple criteria.

        Use for complex queries like "Find all runs over 5km in November" or
        "Show workouts longer than 1 hour".
        """
        return self._call_tool("search_activities", {
            "query": query,
            "start_date": start_date,
            "end_date": end_date,
            "min_distance_km": min_distance_km,
            "min_duration_minutes": min_duration_minutes,
            "limit": limit,
        }, timeout=60)

    # =========================================================================
    # TRAINING & FITNESS
    # =========================================================================

    def get_training_status(self) -> Dict:
        """
        Get TRAINING STATUS: VO2 max, training load (acute/chronic), fitness level.

        Use for questions about overall fitness, VO2 max, or training load management.
        """
        return self._call_tool("get_training_status")

    def get_training_readiness(self) -> Dict:
        """
        Get TRAINING READINESS score and recovery status.

        Score indicates how ready you are for training. Use for workout planning.
        Returns: score, level (PRIME/HIGH/MODERATE/LOW), recovery time, contributing factors.
        """
        return self._call_tool("get_training_readiness")

    # =========================================================================
    # GOALS & PROGRESS
    # =========================================================================

    def get_daily_goals_progress(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get progress toward DAILY GOALS: steps, floors, intensity minutes.

        Shows current value, goal, remaining, and percentage complete.
        Use for questions like "Did I hit my step goal?" or "How close am I to my goals?".
        """
        return self._call_tool("get_daily_goals_progress", {"date_str": date_str})

    def get_step_streak(self) -> Dict:
        """
        Get STEP GOAL STREAK information and consistency stats.

        Returns: current streak, best streak, days achieved in last 60, achievement rate %.
        Use for motivation/consistency questions.
        """
        return self._call_tool("get_step_streak")

    # =========================================================================
    # TRENDS & COMPARISONS
    # =========================================================================

    def get_health_data_for_date_range(
        self,
        start_date: str = Field(..., description="Start date in YYYY-MM-DD format"),
        end_date: str = Field(..., description="End date in YYYY-MM-DD format"),
        metrics: List[str] = Field(
            ["steps", "sleep", "stress", "heart_rate"],
            description="Metrics to include: steps, sleep, stress, heart_rate, body_battery, hrv",
        ),
    ) -> Dict:
        """
        Get health data for a DATE RANGE for trend analysis.

        Use for questions spanning multiple days. Max 90 days.
        Returns daily values for each requested metric.
        """
        return self._call_tool("get_health_data_for_date_range", {
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics,
        }, timeout=120)

    def get_sleep_quality_trends(
        self,
        days: int = Field(
            7,
            description="Number of days to analyze (default 7, max 30)",
        ),
    ) -> Dict:
        """
        Get SLEEP TRENDS over multiple nights with analysis.

        Returns: averages, best/worst nights, daily breakdown with scores and stages.
        Use for questions about sleep patterns or quality over time.
        """
        return self._call_tool("get_sleep_quality_trends", {"days": days}, timeout=60)

    def compare_periods(
        self,
        period1_start: str = Field(..., description="Start of first period (YYYY-MM-DD)"),
        period1_end: str = Field(..., description="End of first period (YYYY-MM-DD)"),
        period2_start: str = Field(..., description="Start of second period (YYYY-MM-DD)"),
        period2_end: str = Field(..., description="End of second period (YYYY-MM-DD)"),
    ) -> Dict:
        """
        COMPARE health metrics between two time periods.

        Perfect for questions like "How does this week compare to last week?" or
        "Am I improving compared to last month?".
        Returns: stats for both periods plus differences and percent changes.
        """
        return self._call_tool("compare_periods", {
            "period1_start": period1_start,
            "period1_end": period1_end,
            "period2_start": period2_start,
            "period2_end": period2_end,
        }, timeout=120)

    # =========================================================================
    # OTHER TOOLS
    # =========================================================================

    def get_devices(self) -> Dict:
        """
        Get information about connected GARMIN DEVICES.

        Returns: device names, software versions, last sync times.
        """
        return self._call_tool("get_devices")

    def get_personal_records(self) -> Dict:
        """
        Get PERSONAL RECORDS/BESTS for various activities.

        Returns: record type, value, and date achieved.
        Use for questions about PRs or best performances.
        """
        return self._call_tool("get_personal_records")

    def get_badges(self) -> Dict:
        """
        Get earned BADGES and achievements.

        Returns: badge names, categories, dates earned, points.
        Use for gamification/achievement questions.
        """
        return self._call_tool("get_badges")

    def get_floors_data(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get FLOORS CLIMBED data for a specific date.

        Returns: floors climbed, floors descended, floor goal.
        """
        return self._call_tool("get_floors_data", {"date_str": date_str})

    def get_all_day_stress(
        self,
        date_str: str = Field(
            "today",
            description="Date in YYYY-MM-DD format, or 'today' for current date",
        ),
    ) -> Dict:
        """
        Get DETAILED STRESS breakdown throughout the day.

        Returns: time spent at each stress level (rest/low/medium/high) in minutes and percentages.
        More detailed than get_stress. Use for understanding stress patterns.
        """
        return self._call_tool("get_all_day_stress", {"date_str": date_str})
