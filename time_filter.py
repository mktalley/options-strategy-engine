from datetime import datetime, time
from zoneinfo import ZoneInfo


class TimeFilter:
    """
    Time-based filter to allow trading only during regular market hours,
    excluding pre-market, after-hours, and end-of-day buffer.
    """
    def __init__(self, tz_name: str = 'America/New_York', end_buffer_minutes: int = 10):
        self.tz = ZoneInfo(tz_name)
        # Regular session: 9:30 to 16:00 local time
        self.start_time = time(9, 30)
        self.end_time = time(16, 0)
        # Minutes to exclude before market close
        self.end_buffer_minutes = end_buffer_minutes

    def is_market_open(self, current_time: datetime = None) -> bool:
        """
        Return True if current_time (or now) is within regular market hours,
        excluding the last end_buffer_minutes.
        """
        now = current_time or datetime.now(self.tz)
        now = now.astimezone(self.tz)
        # Minutes since midnight
        total_minutes = now.hour * 60 + now.minute
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        # Exclude last buffer minutes
        end_buffer = end_minutes - self.end_buffer_minutes
        return start_minutes <= total_minutes < end_buffer
