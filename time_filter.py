from datetime import datetime, time
import os
from zoneinfo import ZoneInfo


class TimeFilter:
    """
    Time-based filter to allow trading only during regular market hours,
    excluding pre-market, after-hours, and end-of-day buffer.
    """

    def __init__(self, time_open: str = None, time_close: str = None, tz_name: str = 'America/New_York', end_buffer_minutes: int = None):
        self.tz = ZoneInfo(tz_name)
        # Load trading window times from environment variables
        open_str = time_open if time_open is not None else os.getenv('MARKET_OPEN_TIME', '09:30')
        close_str = time_close if time_close is not None else os.getenv('MARKET_CLOSE_TIME', '16:00')
        # Parse market open/close times
        try:
            self.start_time = datetime.strptime(open_str, '%H:%M').time()
        except ValueError:
            raise ValueError(f"Invalid MARKET_OPEN_TIME: {open_str}")
        try:
            self.end_time = datetime.strptime(close_str, '%H:%M').time()
        except ValueError:
            raise ValueError(f"Invalid MARKET_CLOSE_TIME: {close_str}")
        # Minutes before market close to stop new trades
        # end_buffer_minutes param overrides environment if provided
        if end_buffer_minutes is not None:
            self.end_buffer_minutes = end_buffer_minutes
        else:
            try:
                self.end_buffer_minutes = int(os.getenv('TIME_FILTER_END_BUFFER_MINUTES', '10'))
            except ValueError:
                self.end_buffer_minutes = 10

        pm_str = os.getenv('PRE_MARKET_START')
        try:
            self.pre_market_start = datetime.strptime(pm_str, '%H:%M').time() if pm_str else None
        except ValueError:
            self.pre_market_start = None
        ah_str = os.getenv('AFTER_HOURS_END')
        try:
            self.after_hours_end = datetime.strptime(ah_str, '%H:%M').time() if ah_str else None
        except ValueError:
            self.after_hours_end = None

    def is_market_open(self, current_time: datetime = None) -> bool:
        """
        Return True if current_time (or now) is within regular market hours,
        excluding the last end_buffer_minutes.
        """
        # Determine reference time, handle naive datetime correctly
        if current_time is None:
            now = datetime.now(self.tz)
        else:
            if current_time.tzinfo is None:
                now = current_time.replace(tzinfo=self.tz)
            else:
                now = current_time.astimezone(self.tz)

        # Minutes since midnight
        total_minutes = now.hour * 60 + now.minute
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        # Exclude last buffer minutes
        end_buffer = end_minutes - self.end_buffer_minutes
        return start_minutes <= total_minutes < end_buffer
