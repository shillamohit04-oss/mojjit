"""
Data Logger — SQLite-Based Simulation Data Storage
===================================================

Logs all simulation data to a SQLite database for analysis
and dashboard visualization.

Tables:
    - sensor_readings:    Temperature, humidity, occupancy data
    - control_actions:    Controller decisions and HVAC states
    - energy_consumption: Power usage and energy tracking
    - comfort_metrics:    Comfort zone compliance
"""

import sqlite3
import os
import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime


class DataLogger:
    """
    SQLite-based data logger for HVAC simulation.

    Provides efficient batch insertion and Pandas DataFrame export
    for dashboard and analysis use.
    """

    def __init__(self, db_path: str = "data/simulation.db"):
        """
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self._buffer = []
        self._buffer_size = 100  # Flush every 100 records

    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                minute INTEGER NOT NULL,
                hour REAL NOT NULL,
                day INTEGER NOT NULL,

                -- Sensor readings (measured, with noise)
                temp_indoor REAL,
                temp_outdoor REAL,
                humidity_indoor REAL,
                humidity_outdoor REAL,
                occupied INTEGER,
                n_occupants INTEGER,
                motion_detected INTEGER,

                -- True values (ground truth)
                temp_indoor_true REAL,
                humidity_indoor_true REAL,
                occupied_true INTEGER,

                -- HVAC state
                hvac_mode TEXT,
                hvac_stage TEXT,
                hvac_action TEXT,
                hvac_power_w REAL,
                hvac_thermal_w REAL,
                protection_active INTEGER,

                -- Energy tracking
                energy_consumed_kwh REAL,
                energy_delivered_kwh REAL,

                -- Comfort metrics
                in_comfort_zone INTEGER,
                comfort_violation_deg REAL,
                pmv_estimate REAL,

                -- Controller info
                controller_type TEXT,

                -- Timestamp
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_minute ON simulation_data(minute)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_controller ON simulation_data(controller_type)
        """)

        self.conn.commit()

    def log(self, data: dict) -> None:
        """
        Log a single timestep of simulation data.

        Args:
            data: Dictionary with keys matching table columns.
        """
        self._buffer.append(data)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        """Write buffered records to the database."""
        if not self._buffer:
            return

        columns = list(self._buffer[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        col_names = ", ".join(columns)

        cursor = self.conn.cursor()
        for record in self._buffer:
            values = [record.get(col) for col in columns]
            cursor.execute(
                f"INSERT INTO simulation_data ({col_names}) VALUES ({placeholders})",
                values
            )

        self.conn.commit()
        self._buffer = []

    def get_dataframe(self, controller_type: Optional[str] = None) -> pd.DataFrame:
        """
        Export simulation data as a Pandas DataFrame.

        Args:
            controller_type: Filter by controller type (optional).

        Returns:
            DataFrame with all simulation data.
        """
        self.flush()  # Ensure all data is written

        query = "SELECT * FROM simulation_data"
        params = []
        if controller_type:
            query += " WHERE controller_type = ?"
            params.append(controller_type)
        query += " ORDER BY minute"

        return pd.read_sql_query(query, self.conn, params=params)

    def get_energy_summary(self, controller_type: Optional[str] = None) -> dict:
        """
        Calculate energy consumption summary.

        Returns dictionary with total energy, average power,
        peak power, and daily averages.
        """
        df = self.get_dataframe(controller_type)
        if df.empty:
            return {}

        total_minutes = df["minute"].max() - df["minute"].min()
        total_days = max(total_minutes / 1440, 1)

        return {
            "total_energy_kwh": float(df["energy_consumed_kwh"].iloc[-1]),
            "avg_power_w": float(df["hvac_power_w"].mean()),
            "peak_power_w": float(df["hvac_power_w"].max()),
            "daily_avg_kwh": float(df["energy_consumed_kwh"].iloc[-1] / total_days),
            "total_runtime_hours": float(
                (df["hvac_stage"] != "OFF").sum() / 60.0
            ),
            "comfort_violation_pct": float(
                (df["in_comfort_zone"] == 0).sum() / len(df) * 100
            ),
            "avg_comfort_violation_deg": float(
                df["comfort_violation_deg"].mean()
            ),
        }

    def clear(self, controller_type: Optional[str] = None) -> None:
        """Clear data from the database."""
        cursor = self.conn.cursor()
        if controller_type:
            cursor.execute(
                "DELETE FROM simulation_data WHERE controller_type = ?",
                (controller_type,)
            )
        else:
            cursor.execute("DELETE FROM simulation_data")
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.flush()
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
