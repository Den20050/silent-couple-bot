"""Time window service for checking user local time."""

from datetime import datetime, time, timedelta

from src.core.constants import (
    EVENING_WINDOW_END,
    EVENING_WINDOW_START,
    MORNING_WINDOW_END,
    MORNING_WINDOW_START,
)


class TimeWindowService:
    """Service for checking if users are in time windows."""
    
    @staticmethod
    def is_in_time_window(
        user_local_time: time,
        window_start: time,
        window_end: time,
    ) -> bool:
        """Check if user's local time is within the specified window.
        
        Args:
            user_local_time: User's local time
            window_start: Window start time
            window_end: Window end time
            
        Returns:
            True if user is in the time window, False otherwise
        """
        if window_start <= window_end:
            # Normal case: window doesn't cross midnight
            return window_start <= user_local_time <= window_end
        else:
            # Window crosses midnight (e.g., 22:00 - 02:00)
            return user_local_time >= window_start or user_local_time <= window_end
    
    @staticmethod
    def get_user_local_time(utc_now: datetime, utc_offset: int) -> time:
        """Get user's local time from UTC time and offset.
        
        Args:
            utc_now: Current UTC datetime
            utc_offset: User's UTC offset in hours
            
        Returns:
            User's local time
        """
        user_local_datetime = utc_now + timedelta(hours=utc_offset)
        return user_local_datetime.time()
    
    @staticmethod
    def is_in_morning_window(user_local_time: time) -> bool:
        """Check if user is in morning time window.
        
        Args:
            user_local_time: User's local time
            
        Returns:
            True if user is in morning window
        """
        return TimeWindowService.is_in_time_window(
            user_local_time,
            MORNING_WINDOW_START,
            MORNING_WINDOW_END,
        )
    
    @staticmethod
    def is_in_evening_window(user_local_time: time) -> bool:
        """Check if user is in evening time window.
        
        Args:
            user_local_time: User's local time
            
        Returns:
            True if user is in evening window
        """
        return TimeWindowService.is_in_time_window(
            user_local_time,
            EVENING_WINDOW_START,
            EVENING_WINDOW_END,
        )

