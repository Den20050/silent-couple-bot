"""Telegram Mini App security (initData verification)."""

import hashlib
import hmac
from urllib.parse import parse_qs, unquote

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


def verify_init_data(init_data: str) -> bool:
    """Verify Telegram Mini App initData signature.
    
    Args:
        init_data: URL-encoded query string from Telegram
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Parse init_data
        params = parse_qs(init_data)
        
        # Extract hash
        hash_value = params.get("hash", [None])[0]
        if not hash_value:
            return False
        
        # Remove hash from params
        del params["hash"]
        
        # Sort params alphabetically
        data_check_string = "\n".join(
            f"{key}={value[0]}" for key, value in sorted(params.items())
        )
        
        # Calculate secret key
        secret_key = hmac.new(
            "WebAppData".encode(),
            settings.tg_bot_token.encode(),
            hashlib.sha256,
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        # Compare
        return hmac.compare_digest(calculated_hash, hash_value)
    except Exception as e:
        logger.error("Error verifying initData", error=str(e))
        return False


def extract_user_id(init_data: str) -> int | None:
    """Extract user ID from init_data.
    
    Args:
        init_data: URL-encoded query string from Telegram
        
    Returns:
        User ID or None if not found
    """
    try:
        params = parse_qs(init_data)
        user_str = params.get("user", [None])[0]
        if not user_str:
            return None
        
        # Parse user JSON
        import json
        user_data = json.loads(unquote(user_str))
        return user_data.get("id")
    except Exception:
        return None

