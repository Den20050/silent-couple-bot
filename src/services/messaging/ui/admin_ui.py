"""Admin UI service for building admin-related messages and keyboards."""

from src.services.messaging.templates import MessageTemplates


class AdminUIService:
    """Service for building admin-related UI elements."""
    
    def format_statistics_message(self, stats: dict[str, int]) -> str:
        """Format statistics message.
        
        Args:
            stats: Statistics dictionary with keys:
                - total_users: Total number of users
                - total_pairs: Total number of pairs
                - single_users: Number of users without pairs
                - pairs_with_demo: Number of pairs with demo
                - users_with_subscription: Number of users with active subscriptions
        
        Returns:
            Formatted message text
        """
        return (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
            f"💑 Всего пар: <b>{stats['total_pairs']}</b>\n"
            f"👤 Одиночных пользователей: <b>{stats['single_users']}</b>\n"
            f"🎁 Пары с демо: <b>{stats['pairs_with_demo']}</b>\n"
            f"💳 Пользователи на подписке: <b>{stats['users_with_subscription']}</b>"
        )

