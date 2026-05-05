"""Garmin Connect integration helpers for recovery and wellness sync."""

from __future__ import annotations

from datetime import date, timedelta
import sqlite3

from garminconnect import Garmin
from garminconnect import GarminConnectAuthenticationError


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
        """Authenticate with Garmin Connect and store the logged-in client.

        Raises:
            ValueError: If credentials are missing.
            RuntimeError: If authentication fails.
        """
        if not self.email or not self.password:
            raise ValueError("Garmin credentials are missing. Set GARMIN_EMAIL and GARMIN_PASSWORD.")

        try:
            client = Garmin(self.email, self.password)
            client.login()
            self.client = client
        except GarminConnectAuthenticationError as exc:
            raise RuntimeError("Garmin login failed. Check GARMIN_EMAIL/GARMIN_PASSWORD.") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Garmin login failed: {exc}") from exc

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
            "sleep_hours": None,
            "sleep_score": None,
            "body_battery_high": None,
            "body_battery_low": None,
            "resting_hr": None,
            "avg_stress": None,
            "hrv_status": None,
            "steps": None,
        }

        try:
            sleep_data = self.client.get_sleep_data(date_str)
            total_sleep_seconds = sleep_data.get("dailySleepDTO", {}).get("sleepTimeSeconds")
            if isinstance(total_sleep_seconds, (int, float)):
                stats["sleep_hours"] = round(total_sleep_seconds / 3600, 2)
            sleep_score = sleep_data.get("sleepScores", {}).get("overall", {}).get("value")
            if isinstance(sleep_score, int):
                stats["sleep_score"] = sleep_score
        except Exception:  # noqa: BLE001
            pass

        try:
            body_battery_data = self.client.get_body_battery(date_str, date_str)
            values = [
                entry.get("bodyBattery")
                for entry in body_battery_data
                if isinstance(entry.get("bodyBattery"), int)
            ]
            if values:
                stats["body_battery_high"] = max(values)
                stats["body_battery_low"] = min(values)
        except Exception:  # noqa: BLE001
            pass

        try:
            rhr_data = self.client.get_rhr_day(date_str)
            resting_hr = rhr_data.get("allMetrics", {}).get("metricsMap", {}).get("WELLNESS_RESTING_HEART_RATE")
            if isinstance(resting_hr, list) and resting_hr:
                first = resting_hr[0]
                value = first.get("value") if isinstance(first, dict) else None
                if isinstance(value, int):
                    stats["resting_hr"] = value
        except Exception:  # noqa: BLE001
            pass

        try:
            stress_data = self.client.get_stress_data(date_str)
            avg_stress = stress_data.get("overallStressLevel")
            if isinstance(avg_stress, int):
                stats["avg_stress"] = avg_stress
        except Exception:  # noqa: BLE001
            pass

        try:
            hrv_data = self.client.get_hrv_data(date_str)
            hrv_status = hrv_data.get("hrvStatus") or hrv_data.get("status")
            if isinstance(hrv_status, str):
                stats["hrv_status"] = hrv_status
        except Exception:  # noqa: BLE001
            pass

        try:
            steps_data = self.client.get_steps_data(date_str)
            if isinstance(steps_data, dict):
                total_steps = steps_data.get("totalSteps")
            else:
                total_steps = None
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
                    SET sleep_hours = ?,
                        sleep_score = ?,
                        body_battery_high = ?,
                        body_battery_low = ?,
                        resting_hr = ?,
                        avg_stress = ?,
                        hrv_status = ?,
                        steps = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND date = ?
                    """,
                    (
                        daily["sleep_hours"],
                        daily["sleep_score"],
                        daily["body_battery_high"],
                        daily["body_battery_low"],
                        daily["resting_hr"],
                        daily["avg_stress"],
                        daily["hrv_status"],
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
                        sleep_hours,
                        sleep_score,
                        body_battery_high,
                        body_battery_low,
                        resting_hr,
                        avg_stress,
                        hrv_status,
                        steps
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        date_str,
                        daily["sleep_hours"],
                        daily["sleep_score"],
                        daily["body_battery_high"],
                        daily["body_battery_low"],
                        daily["resting_hr"],
                        daily["avg_stress"],
                        daily["hrv_status"],
                        daily["steps"],
                    ),
                )

            days_synced += 1

        db_conn.commit()
        return days_synced
