"""Admin UI service for building admin-related messages and keyboards."""

class AdminUIService:
    """Service for building admin-related UI elements."""
    
    def format_statistics_message(self, stats: dict[str, int]) -> str:
        """Format statistics message.
        
        Args:
            stats: Statistics dictionary with keys:
                - total_users: Total number of users
                - total_pairs: Total number of pairs
                - users_without_pairs: Number of users without pairs
                - pairs_with_demo: Number of pairs with demo
                - pairs_with_subscription: Number of pairs with active
                  subscriptions
        
        Returns:
            Formatted message text
        """
        return (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
            f"💑 Всего пар: <b>{stats['total_pairs']}</b>\n"
            f"👤 Пользователи без пар: <b>{stats['users_without_pairs']}</b>\n"
            f"🎁 Пары с демо: <b>{stats['pairs_with_demo']}</b>\n"
            f"💳 Пары на подписке: <b>{stats['pairs_with_subscription']}</b>"
        )

