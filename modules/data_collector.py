"""
Data collector for averaging sensor readings over time
"""
import threading
from typing import Dict, List
from datetime import datetime

from .constants import logger


class DataCollector:
    """Collects and averages sensor data readings"""

    def __init__(self):
        self._lock = threading.Lock()
        self._readings: Dict[str, List[float]] = {}  # param_name -> list of values
        self._last_fetch_time: datetime = None

    def add_reading(self, param_name: str, value: float):
        """Add a sensor reading to the collection"""
        with self._lock:
            if param_name not in self._readings:
                self._readings[param_name] = []
            self._readings[param_name].append(value)

    def add_readings(self, sensors: Dict[str, Dict]):
        """
        Add multiple sensor readings at once

        Args:
            sensors: Dict mapping param_name to {'value': str, 'unit': str}
        """
        with self._lock:
            self._last_fetch_time = datetime.now()
            for param_name, sensor_data in sensors.items():
                try:
                    value = float(sensor_data['value'])
                    if param_name not in self._readings:
                        self._readings[param_name] = []
                    self._readings[param_name].append(value)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid reading for {param_name}: {e}")

    def get_averages(self) -> Dict[str, float]:
        """
        Get average values for all collected readings

        Returns:
            Dict mapping param_name to average value
        """
        with self._lock:
            averages = {}
            for param_name, values in self._readings.items():
                if values:
                    averages[param_name] = sum(values) / len(values)
            return averages

    def get_averages_and_clear(self) -> Dict[str, float]:
        """
        Get average values and clear all collected readings

        Returns:
            Dict mapping param_name to average value
        """
        with self._lock:
            averages = {}
            for param_name, values in self._readings.items():
                if values:
                    averages[param_name] = sum(values) / len(values)

            # Clear all readings after calculating averages
            self._readings.clear()

            return averages

    def get_reading_counts(self) -> Dict[str, int]:
        """
        Get count of readings for each parameter

        Returns:
            Dict mapping param_name to count of readings
        """
        with self._lock:
            return {param: len(values) for param, values in self._readings.items()}

    def clear(self):
        """Clear all collected readings"""
        with self._lock:
            self._readings.clear()

    def get_last_fetch_time(self) -> datetime:
        """Get the timestamp of the last successful data fetch"""
        with self._lock:
            return self._last_fetch_time


# Global data collector instance
data_collector = DataCollector()
