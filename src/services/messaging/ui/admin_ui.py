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

        def _plan_lines(data: dict[str, int], prefix: str = "  •") -> list[str]:
            result = []
            for plan_id in ("1_month", "3_months", "6_months", "1_year", "lifetime"):
                count = data.get(plan_id, 0)
                result.append(f"{prefix} {_PLAN_LABELS[plan_id]}: <b>{count}</b>")
            return result

        by_plan: dict[str, int] = stats.get("subscriptions_by_plan", {})
        gifted: dict[str, int] = stats.get("gifted_by_plan", {})

        paid_total = sum(by_plan.values())
        gift_total = sum(gifted.values())

        if paid_total or gift_total:
            lines.append("")

        if paid_total:
            lines.append(f"💳 <b>Оплаченные подписки ({paid_total}):</b>")
            lines.extend(_plan_lines(by_plan))

        if gift_total:
            if paid_total:
                lines.append("")
            lines.append(f"🎁 <b>Подаренные подписки ({gift_total}):</b>")
            lines.extend(_plan_lines(gifted))

        return "\n".join(lines)

