from datetime import datetime
from .constants import IST


class StatusTracker:
    """In-memory status tracking for datalogger operations"""

    def __init__(self):
        self.last_fetch_success = ""
        self.last_send_success = ""
        self.total_sends = 0
        self.failed_sends = 0
        self.last_error = ""

    def update_fetch_success(self, timestamp: str = None):
        """Update last successful fetch timestamp"""
        if timestamp is None:
            timestamp = datetime.now(IST).isoformat()
        self.last_fetch_success = timestamp

    def update_send_success(self, timestamp: str = None):
        """Update last successful send timestamp"""
        if timestamp is None:
            timestamp = datetime.now(IST).isoformat()
        self.last_send_success = timestamp

    def increment_sends(self):
        """Increment total send counter"""
        self.total_sends += 1

    def increment_failed(self):
        """Increment failed send counter"""
        self.failed_sends += 1

    def set_error(self, error: str):
        """Set last error message"""
        self.last_error = error

    def clear_error(self):
        """Clear error message"""
        self.last_error = ""

    def to_dict(self) -> dict:
        """Convert status to dictionary"""
        return {
            'last_fetch_success': self.last_fetch_success,
            'last_send_success': self.last_send_success,
            'total_sends': self.total_sends,
            'failed_sends': self.failed_sends,
            'last_error': self.last_error
        }


# Global singleton instance
status = StatusTracker()
