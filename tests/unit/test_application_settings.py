"""Unit tests for SettingsApplicationService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.application.settings import SettingsApplicationService
from src.bot.exceptions import (
    UserNotFoundError,
    PairNotFoundError,
    SubscriptionExpiredError,
)
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.settings_ui import SettingsUIService
from src.db.repositories.pairs import PairsRepository


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
def mock_settings_ui():
    """Create mock SettingsUIService."""
    service = MagicMock(spec=SettingsUIService)
    return service


@pytest.fixture
def mock_pairs_repo():
    """Create mock PairsRepository."""
    repo = AsyncMock(spec=PairsRepository)
    return repo


@pytest.fixture
def settings_service(
    mock_session,
    mock_subscription_status_service,
    mock_settings_ui,
):
    """Create SettingsApplicationService with mocked dependencies."""
    return SettingsApplicationService(
        session=mock_session,
        subscription_status_service=mock_subscription_status_service,
        settings_ui=mock_settings_ui,
    )


@pytest.mark.asyncio
async def test_show_settings_success(
    settings_service,
    mock_subscription_status_service,
    mock_settings_ui,
):
    """Test successful settings display."""
    tg_id = 12345
    
    # Setup mocks
    from src.db.models import Pair
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    mock_pair.mode = "chat"
    
    mock_subscription_status_service.get_first_active_pair.return_value = mock_pair
    mock_subscription_status_service.is_subscription_active.return_value = True
    
    mock_settings_ui.build_settings_message.return_value = "⚙️ Настройки\n\nРежим: Чат"
    mock_settings_ui.build_settings_keyboard.return_value = MagicMock()
    mock_settings_ui.build_settings_keyboard.return_value.model_dump.return_value = {"keyboard": []}
    
    # Mock repository
    settings_service._pairs_repo.get_all_by_user_tg_id = AsyncMock(return_value=[mock_pair])
    settings_service._pairs_repo.get_by_id = AsyncMock(return_value=mock_pair)
    settings_service._pairs_repo.get_my_nickname_for_partner = MagicMock(return_value="Партнёр")
    
    from unittest.mock import patch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMock) as mock_validate_user, \
         patch('src.bot.validators.pair.validate_pair_access', new_callable=AsyncMock) as mock_validate_pair_access, \
         patch('src.bot.validators.subscription.validate_subscription_active', new_callable=AsyncMock) as mock_validate_sub:
        
        mock_user = MagicMock()
        mock_user.id = 1
        mock_validate_user.return_value = mock_user
        mock_validate_pair_access.return_value = None
        mock_validate_sub.return_value = None  # No exception means success
        
        # Execute
        success, message_text, reply_markup = await settings_service.show_settings(tg_id=tg_id)
        
        # Assert
        assert success is True
        assert message_text == "⚙️ Настройки\n\nРежим: Чат"
        assert reply_markup is not None
        
        # Verify calls
        mock_subscription_status_service.is_subscription_active.assert_called_with(mock_pair)
        mock_settings_ui.build_settings_message.assert_called_once()
        mock_settings_ui.build_settings_keyboard.assert_called_once()


@pytest.mark.asyncio
async def test_show_settings_user_not_found(settings_service):
    """Test settings display when user is not found."""
    tg_id = 12345
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user:
        mock_validate_user.side_effect = UserNotFoundError(
            tg_id=tg_id,
            message_key="SETTINGS_NO_PAIR",
        )
        
        # Execute & Assert
        with pytest.raises(UserNotFoundError):
            await settings_service.show_settings(tg_id=tg_id)


@pytest.mark.asyncio
async def test_show_settings_pair_not_found(
    settings_service,
    mock_subscription_status_service,
):
    """Test settings display when user has no active pair."""
    tg_id = 12345
    
    mock_subscription_status_service.get_first_active_pair.return_value = None
    
    # Mock repository
    settings_service._pairs_repo.get_all_by_user_tg_id = AsyncMock(return_value=[])
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user:
        mock_user = MagicMock()
        mock_validate_user.return_value = mock_user
        
        # Execute & Assert
        with pytest.raises(PairNotFoundError):
            await settings_service.show_settings(tg_id=tg_id)


@pytest.mark.asyncio
async def test_show_settings_subscription_expired(
    settings_service,
    mock_subscription_status_service,
    mock_settings_ui,
):
    """Test settings display when subscription is expired."""
    tg_id = 12345
    
    # Setup mocks
    from src.db.models import Pair
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    
    mock_subscription_status_service.get_first_active_pair.return_value = mock_pair
    
    # Mock repository
    settings_service._pairs_repo.get_all_by_user_tg_id = AsyncMock(return_value=[mock_pair])
    settings_service._pairs_repo.get_by_id = AsyncMock(return_value=mock_pair)
    
    mock_pay_keyboard = MagicMock()
    mock_pay_keyboard.model_dump.return_value = {"keyboard": [{"text": "Оплатить"}]}
    mock_settings_ui.build_pay_keyboard.return_value = mock_pay_keyboard
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.bot.validators.pair.validate_pair_access', new_callable=AsyncMockPatch) as mock_validate_pair_access, \
         patch('src.bot.validators.subscription.validate_subscription_active', new_callable=AsyncMockPatch) as mock_validate_sub:
        
        mock_user = MagicMock()
        mock_user.id = 1
        mock_validate_user.return_value = mock_user
        mock_validate_pair_access.return_value = None
        mock_validate_sub.side_effect = SubscriptionExpiredError(
            pair_id=mock_pair.id,
            message_key="SETTINGS_SUBSCRIPTION_EXPIRED",
            reply_markup={"keyboard": [{"text": "Оплатить"}]},
        )
        
        # Execute & Assert
        with pytest.raises(SubscriptionExpiredError) as exc_info:
            await settings_service.show_settings(tg_id=tg_id)
        
        assert exc_info.value.reply_markup is not None

