"""Custom exceptions for bot handlers."""

from typing import Optional


class BotException(Exception):
    """Base exception for bot-related errors."""
    
    def __init__(
        self,
        message_key: str,
        message: Optional[str] = None,
        show_alert: bool = False,
        reply_markup: Optional[dict] = None,
    ) -> None:
        """Initialize bot exception.
        
        Args:
            message_key: Message key for localization
            message: Optional pre-formatted message
            show_alert: Whether to show alert in Telegram
            reply_markup: Optional reply markup for error response
        """
        super().__init__(message or message_key)
        self.message_key = message_key
        self.message = message
        self.show_alert = show_alert
        self.reply_markup = reply_markup


class ValidationError(BotException):
    """Exception raised when validation fails."""
    pass


class UserNotFoundError(ValidationError):
    """Exception raised when user is not found."""
    
    def __init__(
        self,
        tg_id: int,
        message_key: str = "MENU_USER_NOT_FOUND",
        message: Optional[str] = None,
    ) -> None:
        """Initialize user not found error.
        
        Args:
            tg_id: Telegram user ID that was not found
            message_key: Message key for error
            message: Optional pre-formatted message
        """
        super().__init__(message_key, message)
        self.tg_id = tg_id


class PairNotFoundError(ValidationError):
    """Exception raised when pair is not found."""
    
    def __init__(
        self,
        pair_id: Optional[int] = None,
        tg_id: Optional[int] = None,
        message_key: str = "SETTINGS_NO_PAIR",
        message: Optional[str] = None,
    ) -> None:
        """Initialize pair not found error.
        
        Args:
            pair_id: Optional pair ID that was not found
            tg_id: Optional Telegram user ID
            message_key: Message key for error
            message: Optional pre-formatted message
        """
        super().__init__(message_key, message)
        self.pair_id = pair_id
        self.tg_id = tg_id


class PairAccessDeniedError(ValidationError):
    """Exception raised when user doesn't have access to pair."""
    
    def __init__(
        self,
        user_id: Optional[int] = None,
        pair_id: Optional[int] = None,
        tg_id: Optional[int] = None,
        message_key: str = "SETTINGS_NO_PAIR",
        message: Optional[str] = None,
    ) -> None:
        """Initialize pair access denied error.
        
        Args:
            user_id: Optional user ID that was denied access
            pair_id: Optional pair ID
            tg_id: Optional Telegram user ID
            message_key: Message key for error
            message: Optional pre-formatted message
        """
        super().__init__(message_key, message)
        self.user_id = user_id
        self.pair_id = pair_id
        self.tg_id = tg_id


class SubscriptionNotFoundError(ValidationError):
    """Exception raised when subscription is not found."""
    
    def __init__(
        self,
        pair_id: int,
        message_key: str = "PAY_SUBSCRIPTION_NOT_FOUND",
        message: Optional[str] = None,
    ) -> None:
        """Initialize subscription not found error.
        
        Args:
            pair_id: Pair ID
            message_key: Message key for error
            message: Optional pre-formatted message
        """
        super().__init__(message_key, message)
        self.pair_id = pair_id


class SubscriptionExpiredError(ValidationError):
    """Exception raised when subscription is expired."""
    
    def __init__(
        self,
        pair_id: int,
        message_key: str = "SETTINGS_SUBSCRIPTION_EXPIRED",
        message: Optional[str] = None,
        show_pay_button: bool = True,
        reply_markup: Optional[dict] = None,
    ) -> None:
        """Initialize subscription expired error.
        
        Args:
            pair_id: Pair ID
            message_key: Message key for error
            message: Optional pre-formatted message
            show_pay_button: Whether to include pay keyboard
            reply_markup: Optional reply markup
        """
        super().__init__(message_key, message, show_alert=False, reply_markup=reply_markup)
        self.pair_id = pair_id
        self.show_pay_button = show_pay_button


class BusinessLogicError(BotException):
    """Exception raised when business logic validation fails."""
    pass


class PaymentError(BusinessLogicError):
    """Exception raised when payment operation fails."""
    
    def __init__(
        self,
        message_key: str = "PAY_ERROR",
        message: Optional[str] = None,
        tg_id: Optional[int] = None,
        pair_id: Optional[int] = None,
    ) -> None:
        """Initialize payment error.
        
        Args:
            message_key: Message key for error
            message: Optional pre-formatted message
            tg_id: Optional Telegram user ID
            pair_id: Optional pair ID
        """
        super().__init__(message_key, message)
        self.tg_id = tg_id
        self.pair_id = pair_id

