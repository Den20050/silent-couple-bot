"""Unit tests for SubscriptionApplicationService."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, User as TelegramUser

from src.services.application.subscription import SubscriptionApplicationService
from src.bot.exceptions import UserNotFoundError, PairNotFoundError
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.menu_ui import MenuUIService


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
def mock_menu_ui():
    """Create mock MenuUIService."""
    service = MagicMock(spec=MenuUIService)
    return service


@pytest.fixture
def subscription_service(
    mock_session,
    mock_subscription_status_service,
    mock_menu_ui,
):
    """Create SubscriptionApplicationService with mocked dependencies."""
    return SubscriptionApplicationService(
        session=mock_session,
        subscription_status_service=mock_subscription_status_service,
        menu_ui=mock_menu_ui,
    )


@pytest.fixture
def mock_callback():
    """Create mock CallbackQuery."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TelegramUser)
    callback.from_user.id = 12345
    return callback


@pytest.mark.asyncio
async def test_show_subscription_info_success(
    subscription_service,
    mock_callback,
    mock_subscription_status_service,
    mock_menu_ui,
):
    """Test successful subscription info retrieval."""
    # Setup mocks
    from src.db.models import Pair
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    
    mock_pair.status = "active"
    mock_pair.uid_a = 1
    mock_pair.uid_b = 2

    mock_subscription_status_service.get_subscription_info.return_value = (
        False,       # is_trial
        10,          # days_left
        False,       # is_expired
        "1_month",   # tariff_name
        False,       # is_lifetime
    )
    
    mock_menu_ui.build_subscription_info_message.return_value = "Подписка активна: 10 дней"
    mock_menu_ui.build_subscription_keyboard.return_value = MagicMock()
    
    # Mock validators and repositories used inside service
    from unittest.mock import patch, AsyncMock as AsyncMockPatch

    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.db.repositories.pairs.PairsRepository') as mock_pairs_repo_cls, \
         patch('src.db.repositories.users.UsersRepository') as mock_users_repo_cls, \
         patch('src.bot.handlers.start.services.pair_service.format_partner_text') as mock_format_partner_text:

        mock_user = MagicMock()
        mock_user.id = 1
        mock_validate_user.return_value = mock_user

        mock_pairs_repo = AsyncMock()
        mock_pairs_repo.get_all_by_user_tg_id = AsyncMock(return_value=[mock_pair])
        mock_pairs_repo.get_my_nickname_for_partner = MagicMock(return_value="Партнёр")
        mock_pairs_repo_cls.return_value = mock_pairs_repo

        mock_partner = MagicMock()
        mock_partner.username = "partner"
        mock_users_repo = AsyncMock()
        mock_users_repo.get_by_id = AsyncMock(return_value=mock_partner)
        mock_users_repo_cls.return_value = mock_users_repo

        mock_format_partner_text.return_value = "partner"
        
        # Execute
        success, message_text, keyboard = await subscription_service.show_subscription_info(
            callback=mock_callback,
        )
        
        # Assert
        assert success is True
        assert message_text == "Подписка активна: 10 дней"
        assert keyboard is not None
        
        # Verify calls
        mock_subscription_status_service.get_subscription_info.assert_called_once_with(mock_pair)
        mock_menu_ui.build_subscription_info_message.assert_called_once_with(
            days_left=10,
            is_trial=False,
            is_expired=False,
            partner_text="partner",
            tariff_name="1_month",
            is_lifetime=False,
        )
        mock_menu_ui.build_subscription_keyboard.assert_called_once()


@pytest.mark.asyncio
async def test_show_subscription_info_user_not_found(
    subscription_service,
    mock_callback,
):
    """Test subscription info when user is not found."""
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user:
        mock_validate_user.side_effect = UserNotFoundError(
            tg_id=12345,
            message_key="MENU_USER_NOT_FOUND",
        )
        
        # Execute & Assert
        with pytest.raises(UserNotFoundError):
            await subscription_service.show_subscription_info(
                callback=mock_callback,
            )


@pytest.mark.asyncio
async def test_show_subscription_info_pair_not_found(
    subscription_service,
    mock_callback,
):
    """Test subscription info when user has no pair."""
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.db.repositories.pairs.PairsRepository') as mock_pairs_repo_cls:

        mock_user = MagicMock()
        mock_user.id = 1
        mock_validate_user.return_value = mock_user

        mock_pairs_repo = AsyncMock()
        mock_pairs_repo.get_all_by_user_tg_id = AsyncMock(return_value=[])
        mock_pairs_repo_cls.return_value = mock_pairs_repo
        
        # Execute & Assert
        with pytest.raises(PairNotFoundError):
            await subscription_service.show_subscription_info(
                callback=mock_callback,
            )


@pytest.mark.asyncio
async def test_show_subscription_info_trial(
    subscription_service,
    mock_callback,
    mock_subscription_status_service,
    mock_menu_ui,
):
    """Test subscription info for trial subscription."""
    # Setup mocks
    from src.db.models import Pair
    mock_pair = MagicMock(spec=Pair)
    mock_pair.id = 1
    
    mock_pair.status = "trial"
    mock_pair.uid_a = 1
    mock_pair.uid_b = 2

    mock_subscription_status_service.get_subscription_info.return_value = (
        True,        # is_trial
        5,           # days_left
        False,       # is_expired
        "trial",     # tariff_name
        False,       # is_lifetime
    )
    
    mock_menu_ui.build_subscription_info_message.return_value = "Демо период: 5 дней"
    mock_menu_ui.build_subscription_keyboard.return_value = MagicMock()
    
    from unittest.mock import patch, AsyncMock as AsyncMockPatch
    
    with patch('src.bot.validators.user.validate_user_exists', new_callable=AsyncMockPatch) as mock_validate_user, \
         patch('src.db.repositories.pairs.PairsRepository') as mock_pairs_repo_cls, \
         patch('src.db.repositories.users.UsersRepository') as mock_users_repo_cls, \
         patch('src.bot.handlers.start.services.pair_service.format_partner_text') as mock_format_partner_text:

        mock_user = MagicMock()
        mock_user.id = 1
        mock_validate_user.return_value = mock_user

        mock_pairs_repo = AsyncMock()
        mock_pairs_repo.get_all_by_user_tg_id = AsyncMock(return_value=[mock_pair])
        mock_pairs_repo.get_my_nickname_for_partner = MagicMock(return_value="Партнёр")
        mock_pairs_repo_cls.return_value = mock_pairs_repo

        mock_partner = MagicMock()
        mock_partner.username = "partner"
        mock_users_repo = AsyncMock()
        mock_users_repo.get_by_id = AsyncMock(return_value=mock_partner)
        mock_users_repo_cls.return_value = mock_users_repo

        mock_format_partner_text.return_value = "partner"
        
        # Execute
        success, message_text, keyboard = await subscription_service.show_subscription_info(
            callback=mock_callback,
        )
        
        # Assert
        assert success is True
        assert message_text == "Демо период: 5 дней"
        
        # Verify trial-specific call
        mock_menu_ui.build_subscription_info_message.assert_called_once_with(
            days_left=5,
            is_trial=True,
            is_expired=False,
            partner_text="partner",
            tariff_name="trial",
            is_lifetime=False,
        )

