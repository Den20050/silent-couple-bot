"""Admin UI service for building admin-related messages and keyboards."""

_PLAN_LABELS = {
    "1_month":  "1 месяц",
    "3_months": "3 месяца",
    "6_months": "6 месяцев",
    "1_year":   "1 год",
    "lifetime": "Навсегда",
}


class AdminUIService:
    """Service for building admin-related UI elements."""

    def format_statistics_message(self, stats: dict) -> str:
        """Format statistics message.

        Args:
            stats: Statistics dictionary with keys:
                - total_users: Total number of users
                - total_pairs: Total number of pairs (each pair = 1 unit)
                - users_without_pairs: Consented users not in any pair
                - pairs_with_demo: Pairs in trial status
                - pairs_with_subscription: Pairs with active subscription
                - subscriptions_by_plan: dict plan_id → pair count

        Returns:
            Formatted message text
        """
        total = stats['total_users']
        in_pairs = stats.get('users_in_pairs', total - stats['users_without_pairs'])
        solo = stats['users_without_pairs']

        lines = [
            "📊 <b>Статистика бота</b>\n",
            f"👥 Пользователей (с согласием): <b>{total}</b>",
            f"  👫 В паре(ах): <b>{in_pairs}</b>",
            f"  👤 Без пары: <b>{solo}</b>",
            f"  ✅ Итого: {in_pairs} + {solo} = <b>{in_pairs + solo}</b>\n",
            f"💑 Всего пар: <b>{stats['total_pairs']}</b>",
            f"  🎁 На демо: <b>{stats['pairs_with_demo']}</b>",
            f"  💳 На подписке: <b>{stats['pairs_with_subscription']}</b>",
        ]

        by_plan: dict[str, int] = stats.get("subscriptions_by_plan", {})
        if by_plan:
            lines.append("\n📋 <b>Подписки по тарифам:</b>")
            for plan_id in ("1_month", "3_months", "6_months", "1_year", "lifetime"):
                count = by_plan.get(plan_id, 0)
                label = _PLAN_LABELS[plan_id]
                lines.append(f"  • {label}: <b>{count}</b>")

        return "\n".join(lines)

