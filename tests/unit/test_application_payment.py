"""Unit tests for PaymentApplicationService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.application.payment import PaymentApplicationService
from src.bot.exceptions import (
    UserNotFoundError,
    PairNotFoundError,
    SubscriptionNotFoundError,
    PaymentError,
)
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.payment_ui import PaymentUIService
from src.core.protocols.payment import PaymentServiceProtocol
from src.core.protocols.bot_provider import BotProviderProtocol


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_subscription_status_service():
    """Create mock SubscriptionStatusService."""
    service = AsyncMock(spec=SubscriptionStatusService)
    return service


@pytest.fixture
def mock_payment_ui():
    """Create mock PaymentUIService."""
    service = MagicMock(spec=PaymentUIService)
    return service


@pytest.fixture
def mock_payment_service():
    """Create mock PaymentServiceProtocol."""
    service = AsyncMock(spec=PaymentServiceProtocol)
    return service


@pytest.fixture
def mock_bot_provider():
    """Create mock BotProviderProtocol."""
    provider = MagicMock(spec=BotProviderProtocol)
    bot = MagicMock()
    bot_info = MagicMock()
    bot_info.username = "test_bot"
    bot.get_me = AsyncMock(return_value=bot_info)
    provider.get_bot.return_value = bot
    return provider


@pytest.fixture
def mock_currency_rates_service():
    """Create mock CurrencyRatesService."""
    service = AsyncMock()
    # For RUB, service should just return the original RUB price (no conversion).
    service.calculate_price_in_currency = AsyncMock(side_effect=lambda rub_price, currency_code: rub_price)
    return service


@pytest.fixture
def mock_settings():
    """Create mock Settings."""
    settings = MagicMock()
    settings.get_subscription_prices.return_value = {
        "RUB": {"1_month": 299, "lifetime": 4999},
        "USD": {"1_month": 5, "lifetime": 50},
    }
    return settings


@pytest.fixture
def payment_service(
    mock_session,
    mock_subscription_status_service,
    mock_payment_ui,
    mock_payment_service,
    mock_bot_provider,
    mock_settings,
    mock_currency_rates_service,
):
    """Create PaymentApplicationService with mocked dependencies."""
    return PaymentApplicationService(
        session=mock_session,
        subscription_status_service=mock_subscription_status_service,
        payment_ui=mock_payment_ui,
        payment_service=mock_payment_service,
        bot_provider=mock_bot_provider,
        settings=mock_settings,
        currency_rates_service=mock_currency_rates_service,
    )


@pytest.mark.asyncio
async def test_show_currencies_success(
    payment_service,
    mock_subscription_status_service,
    mock_payment_ui,
):
    """Test successful currency selection display."""
    tg_id = 12345
    
    # Setup mocks
    from src.db.models import Pair, Subscription
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    mock_subscription = MagicMock(spec=Subscription)
    
    mock_subscription_status_service.check_subscription_for_payment.return_value = (
        True,   # can_pay
        None,   # error_key
    )
    
    mock_payment_ui.build_currencies_keyboard.return_value = MagicMock()
    
    from unittest.mock import patch
    
    with patch('src.bot.validators.user.validate_user_exists') as mock_validate_user, \
         patch('src.bot.validators.pair.validate_user_has_pair') as mock_validate_pair, \
         patch('src.bot.validators.subscription.validate_subscription_exists') as mock_validate_sub:
        
        mock_user = MagicMock()
        mock_validate_user.return_value = mock_user
        mock_validate_pair.return_value = mock_pair
        mock_validate_sub.return_value = mock_subscription
        
        # Execute
        success, message_text, keyboard = await payment_service.show_currencies(tg_id=tg_id)
        
        # Assert
        assert success is True
        assert keyboard is not None
        
        # Verify calls
        mock_subscription_status_service.check_subscription_for_payment.assert_called_once_with(mock_pair)
        mock_payment_ui.build_currencies_keyboard.assert_called_once()


@pytest.mark.asyncio
async def test_show_currencies_user_not_found(payment_service):
    """Test currency selection when user is not found."""
    tg_id = 12345
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user:
        mock_validate_user.side_effect = UserNotFoundError(
            tg_id=tg_id,
            message_key="PAY_START_REQUIRED",
        )
        
        # Execute & Assert
        with pytest.raises(UserNotFoundError):
            await payment_service.show_currencies(tg_id=tg_id)


@pytest.mark.asyncio
async def test_show_currencies_pair_not_found(payment_service):
    """Test currency selection when user has no pair."""
    tg_id = 12345
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.bot.validators.pair.validate_user_has_pair', new_callable=AsyncMockPatch) as mock_validate_pair:
        
        mock_user = MagicMock()
        mock_validate_user.return_value = mock_user
        mock_validate_pair.side_effect = PairNotFoundError(
            tg_id=tg_id,
            message_key="PAY_NO_PAIR",
        )
        
        # Execute & Assert
        with pytest.raises(PairNotFoundError):
            await payment_service.show_currencies(tg_id=tg_id)


@pytest.mark.asyncio
async def test_show_currencies_subscription_not_found(payment_service):
    """Test currency selection when subscription is not found."""
    tg_id = 12345
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.bot.validators.pair.validate_user_has_pair', new_callable=AsyncMockPatch) as mock_validate_pair, \
         patch('src.bot.validators.subscription.validate_subscription_exists', new_callable=AsyncMockPatch) as mock_validate_sub:
        
        mock_user = MagicMock()
        mock_pair = MagicMock()
        mock_validate_user.return_value = mock_user
        mock_validate_pair.return_value = mock_pair
        mock_validate_sub.side_effect = SubscriptionNotFoundError(
            pair_id=mock_pair.id,
            message_key="PAY_SUBSCRIPTION_NOT_FOUND",
        )
        
        # Execute & Assert
        with pytest.raises(SubscriptionNotFoundError):
            await payment_service.show_currencies(tg_id=tg_id)


@pytest.mark.asyncio
async def test_show_currencies_subscription_lifetime(
    payment_service,
    mock_subscription_status_service,
):
    """Test currency selection when subscription is lifetime."""
    tg_id = 12345
    
    # Setup mocks
    from src.db.models import Pair, Subscription
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    mock_subscription = MagicMock(spec=Subscription)
    
    mock_subscription_status_service.check_subscription_for_payment.return_value = (
        False,  # can_pay
        "PAY_SUBSCRIPTION_LIFETIME",  # error_key
    )
    
    from unittest.mock import patch
    
    with patch('src.bot.validators.user.validate_user_exists') as mock_validate_user, \
         patch('src.bot.validators.pair.validate_user_has_pair') as mock_validate_pair, \
         patch('src.bot.validators.subscription.validate_subscription_exists') as mock_validate_sub:
        
        mock_user = MagicMock()
        mock_validate_user.return_value = mock_user
        mock_validate_pair.return_value = mock_pair
        mock_validate_sub.return_value = mock_subscription
        
        # Execute & Assert
        with pytest.raises(PaymentError) as exc_info:
            await payment_service.show_currencies(tg_id=tg_id)
        
        assert exc_info.value.message_key == "PAY_SUBSCRIPTION_LIFETIME"


@pytest.mark.asyncio
async def test_create_payment_for_tariff_success(
    payment_service,
    mock_subscription_status_service,
    mock_payment_service,
    mock_payment_ui,
    mock_bot_provider,
):
    """Test successful payment creation."""
    tg_id = 12345
    plan_id = "1_month"
    currency_code = "RUB"
    
    # Setup mocks
    from src.db.models import Pair, Subscription
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    mock_subscription = MagicMock(spec=Subscription)
    
    mock_subscription_status_service.check_subscription_for_payment.return_value = (
        True,   # can_pay
        None,   # error_key
    )
    
    mock_payment_response = {
        "id": "payment_123",
        "confirmation": {
            "confirmation_url": "https://pay.example.com/pay",
        },
    }
    mock_payment_service.create_payment.return_value = mock_payment_response
    
    mock_payment_ui.build_payment_keyboard.return_value = MagicMock()
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.bot.validators.pair.validate_user_has_pair', new_callable=AsyncMockPatch) as mock_validate_pair, \
         patch('src.bot.validators.subscription.validate_subscription_exists', new_callable=AsyncMockPatch) as mock_validate_sub:
        
        mock_user = MagicMock()
        mock_validate_user.return_value = mock_user
        mock_validate_pair.return_value = mock_pair
        mock_validate_sub.return_value = mock_subscription
        
        # Execute
        success, message_text, keyboard = await payment_service.create_payment_for_tariff(
            tg_id=tg_id,
            plan_id=plan_id,
            currency_code=currency_code,
        )
        
        # Assert
        assert success is True
        assert keyboard is not None
        
        # Verify payment creation
        mock_payment_service.create_payment.assert_called_once()
        call_kwargs = mock_payment_service.create_payment.call_args[1]
        assert call_kwargs["pair_id"] == mock_pair.id
        assert call_kwargs["currency"] == currency_code
        assert call_kwargs["is_lifetime"] is False

