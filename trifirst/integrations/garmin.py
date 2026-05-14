"""Garmin Connect integration helpers for recovery and wellness sync."""

from __future__ import annotations

from datetime import date, timedelta
import sqlite3

from garminconnect import Garmin
from garminconnect import GarminConnectAuthenticationError
#for chache so it doesnt log into garmin every sync
_garmin_session_cache: dict = {}


class GarminClient:
    """Simple client wrapper for Garmin Connect recovery metrics."""

    def __init__(self, email: str, password: str) -> None:
        """Store Garmin credentials and initialize a disconnected client.

        Args:
            email: Garmin Connect account email.
            password: Garmin Connect account password.
        """
        self.email = email
        self.password = password
        self.client: Garmin | None = None

    def connect(self) -> None:
        """Authenticate with Garmin Connect, reusing cached session if available."""
        cache_key = self.email
        if cache_key in _garmin_session_cache:
            self.client = _garmin_session_cache[cache_key]
            return
        try:
            self.client.login()
            _garmin_session_cache[cache_key] = self.client
        except Exception as exc:
            raise RuntimeError("Garmin login failed. Check credentials.") from exc

    def get_daily_stats(self, date_str: str) -> dict[str, int | float | str | None]:
        """Fetch Garmin recovery stats for a single day.

        Args:
            date_str: Target date in ISO format YYYY-MM-DD.

        Returns:
            Dict containing sleep, body battery, HR, stress, HRV, and steps fields.
        """
        if self.client is None:
            raise RuntimeError("Garmin client not connected. Call connect() first.")

        stats: dict[str, int | float | str | None] = {
            "date": date_str,
            "body_battery_high": None,
            "body_battery_low": None,
            "resting_hr": None,
            "avg_sleep_hr": None,
            "hrv_avg": None,
            "hrv_status": None,
            "body_battery_change": None,
            "avg_resting_hr_7day": None,
            "steps": None,
        }

        try:
            sleep_data = self.client.get_sleep_data(date_str)
            if isinstance(sleep_data.get("restingHeartRate"), int):
                stats["resting_hr"] = sleep_data["restingHeartRate"]
            if isinstance(sleep_data.get("avgOvernightHrv"), (int, float)):
                stats["hrv_avg"] = float(sleep_data["avgOvernightHrv"])
            if isinstance(sleep_data.get("hrvStatus"), str):
                stats["hrv_status"] = sleep_data["hrvStatus"]
            if isinstance(sleep_data.get("bodyBatteryChange"), int):
                stats["body_battery_change"] = sleep_data["bodyBatteryChange"]

            sleep_body_battery = sleep_data.get("sleepBodyBattery")
            if isinstance(sleep_body_battery, list) and sleep_body_battery:
                first_entry = sleep_body_battery[0] if isinstance(sleep_body_battery[0], dict) else None
                last_entry = sleep_body_battery[-1] if isinstance(sleep_body_battery[-1], dict) else None
                first_value = first_entry.get("value") if first_entry else None
                last_value = last_entry.get("value") if last_entry else None
                if isinstance(first_value, int):
                    stats["body_battery_low"] = first_value
                if isinstance(last_value, int):
                    stats["body_battery_high"] = last_value

            sleep_heart_rate = sleep_data.get("sleepHeartRate")
            if isinstance(sleep_heart_rate, list):
                hr_values = []
                for entry in sleep_heart_rate:
                    if isinstance(entry, dict):
                        value = entry.get("value")
                        if isinstance(value, (int, float)):
                            hr_values.append(float(value))
                if hr_values:
                    stats["avg_sleep_hr"] = sum(hr_values) / len(hr_values)
        except Exception:  # noqa: BLE001
            pass

        try:
            heart_rates = self.client.get_heart_rates(date_str)
            if isinstance(heart_rates.get("restingHeartRate"), int) and stats["resting_hr"] is None:
                stats["resting_hr"] = heart_rates["restingHeartRate"]
            if isinstance(heart_rates.get("lastSevenDaysAvgRestingHeartRate"), int):
                stats["avg_resting_hr_7day"] = heart_rates["lastSevenDaysAvgRestingHeartRate"]
        except Exception:  # noqa: BLE001
            pass

        try:
            steps_data = self.client.get_steps_data(date_str)
            total_steps: int | None = None
            if isinstance(steps_data, list):
                step_values = [
                    item.get("steps")
                    for item in steps_data
                    if isinstance(item, dict) and isinstance(item.get("steps"), int)
                ]
                if step_values:
                    total_steps = sum(step_values)
            elif isinstance(steps_data, dict) and isinstance(steps_data.get("totalSteps"), int):
                total_steps = steps_data.get("totalSteps")
            if isinstance(total_steps, int):
                stats["steps"] = total_steps
        except Exception:  # noqa: BLE001
            pass

        return stats

    def sync_stats(self, user_id: int, db_conn: sqlite3.Connection, days: int = 7) -> int:
        """Sync Garmin daily stats for the most recent N days into the database.

        Args:
            user_id: Local application user ID.
            db_conn: Active SQLite connection.
            days: Number of most recent days to sync.

        Returns:
            Count of successfully processed days.
        """
        days_synced = 0
        today = date.today()

        for offset in range(days):
            target_date = today - timedelta(days=offset)
            date_str = target_date.isoformat()
            daily = self.get_daily_stats(date_str)

            existing = db_conn.execute(
                "SELECT id FROM garmin_daily_stats WHERE user_id = ? AND date = ?",
                (user_id, date_str),
            ).fetchone()

            if existing:
                db_conn.execute(
                    """
                    UPDATE garmin_daily_stats
                    SET body_battery_high = ?,
                        body_battery_low = ?,
                        resting_hr = ?,
                        avg_sleep_hr = ?,
                        hrv_avg = ?,
                        hrv_status = ?,
                        body_battery_change = ?,
                        avg_resting_hr_7day = ?,
                        steps = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND date = ?
                    """,
                    (
                        daily["body_battery_high"],
                        daily["body_battery_low"],
                        daily["resting_hr"],
                        daily["avg_sleep_hr"],
                        daily["hrv_avg"],
                        daily["hrv_status"],
                        daily["body_battery_change"],
                        daily["avg_resting_hr_7day"],
                        daily["steps"],
                        user_id,
                        date_str,
                    ),
                )
            else:
                db_conn.execute(
                    """
                    INSERT INTO garmin_daily_stats (
                        user_id,
                        date,
                        body_battery_high,
                        body_battery_low,
                        resting_hr,
                        avg_sleep_hr,
                        hrv_avg,
                        hrv_status,
                        body_battery_change,
                        avg_resting_hr_7day,
                        steps
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        date_str,
                        daily["body_battery_high"],
                        daily["body_battery_low"],
                        daily["resting_hr"],
                        daily["avg_sleep_hr"],
                        daily["hrv_avg"],
                        daily["hrv_status"],
                        daily["body_battery_change"],
                        daily["avg_resting_hr_7day"],
                        daily["steps"],
                    ),
                )

            days_synced += 1

        db_conn.commit()
        return days_synced
