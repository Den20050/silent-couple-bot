"""Admin UI service for building admin-related messages and keyboards."""

from decimal import Decimal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.constants import SUPPORTED_CURRENCIES
from src.core.messages import get_message

_PLAN_LABELS = {
    "1_month": "1 месяц",
    "3_months": "3 месяца",
    "6_months": "6 месяцев",
    "1_year": "1 год",
    "lifetime": "Навсегда",
}

_PERIOD_OPTIONS: list[tuple[str, int | None]] = [
    ("7 дн.", 7),
    ("30 дн.", 30),
    ("90 дн.", 90),
    ("Всё", None),
]

_TAB_OPTIONS: list[tuple[str, str]] = [
    ("👥 Пользователи", "users"),
    ("💰 Оплата", "payments"),
]


class AdminUIService:
    """Service for building admin-related UI elements."""

    def _period_token(self, period_days: int | None) -> str:
        return "all" if period_days is None else str(period_days)

    def _stats_callback(self, tab: str, period_days: int | None) -> str:
        return f"admin_stats_view:{tab}:{self._period_token(period_days)}"

    def build_stats_keyboard(
        self,
        selected_tab: str,
        selected_period_days: int | None,
    ) -> InlineKeyboardMarkup:
        """Build tab + period selector for admin statistics."""
        tab_row = []
        for label, tab in _TAB_OPTIONS:
            suffix = " ✓" if tab == selected_tab else ""
            tab_row.append(
                InlineKeyboardButton(
                    text=f"{label}{suffix}",
                    callback_data=self._stats_callback(tab, selected_period_days),
                )
            )

        period_row = []
        for label, days in _PERIOD_OPTIONS:
            suffix = " ✓" if days == selected_period_days else ""
            period_row.append(
                InlineKeyboardButton(
                    text=f"{label}{suffix}",
                    callback_data=self._stats_callback(selected_tab, days),
                )
            )

        return InlineKeyboardMarkup(
            inline_keyboard=[
                tab_row,
                period_row,
                [
                    InlineKeyboardButton(
                        text=get_message("MENU_BACK_BUTTON"),
                        callback_data="menu_back",
                    ),
                ],
            ]
        )

    def format_statistics_message(self, stats: dict) -> str:
        """Format statistics message for the active tab."""
        if stats.get("stats_tab") == "payments":
            return self.format_payment_statistics_message(stats)
        return self.format_user_statistics_message(stats)

    def format_user_statistics_message(self, stats: dict) -> str:
        """Format user-centric statistics."""
        period_label = stats.get("period_label", "30 дн.")
        in_pairs = stats.get("users_in_pairs", 0)
        solo = stats.get("users_without_pairs", 0)
        solo_no_mode = stats.get("solo_no_mode", 0)
        solo_waiting = stats.get("solo_waiting_partner", 0)

        pairs_scope = (
            "созданные за период"
            if stats.get("period_days") is not None
            else "всего"
        )

        lines = [
            f"👥 <b>Пользователи · {period_label}</b>\n",
            f"  Всего с согласием: <b>{stats['total_users']}</b>",
            f"  Новых за период: <b>{stats.get('new_users', 0)}</b>",
            f"  В паре(ах) сейчас: <b>{in_pairs}</b>",
            "",
            "👤 <b>Одиночные сейчас</b> (без пары): "
            f"<b>{solo}</b>",
            f"  • зашли, не выбрали режим: <b>{solo_no_mode}</b>",
            f"  • выбрали режим, ждут партнёра: <b>{solo_waiting}</b>",
            f"  • новых за период и без пары: "
            f"<b>{stats.get('new_solo_in_period', 0)}</b>",
            "",
            f"💑 <b>Пары ({pairs_scope})</b>: <b>{stats['total_pairs']}</b>",
            f"  🟢 используют бот (демо/подписка): "
            f"<b>{stats.get('pairs_using_bot', 0)}</b>",
            f"  🎁 на демо: <b>{stats['pairs_with_demo']}</b>",
            f"  💳 на подписке: <b>{stats['pairs_with_subscription']}</b>",
            f"  🔴 без оплаты (past_due): <b>{stats.get('pairs_past_due', 0)}</b>",
        ]

        if stats.get("pairs_cancelled", 0):
            lines.append(
                f"  ⚫ отменены: <b>{stats['pairs_cancelled']}</b>"
            )

        return "\n".join(lines)

    def format_payment_statistics_message(self, stats: dict) -> str:
        """Format payment-centric statistics (counts are per pair)."""
        period_label = stats.get("period_label", "30 дн.")
        paid_pairs = stats.get("paid_pairs", 0)
        paid_transactions = stats.get("paid_transactions", 0)

        lines = [
            f"💰 <b>Оплата · {period_label}</b>",
            "<i>Единица учёта: пара (1 оплата = 1 пара)</i>\n",
            f"Оплатили: <b>{paid_pairs}</b> "
            f"{'пара' if paid_pairs == 1 else 'пар'}",
        ]

        if paid_transactions:
            lines.append(
                f"Транзакций за период: <b>{paid_transactions}</b>"
            )

        plan_lines = self._plan_lines(stats.get("payments_by_plan", {}))
        if plan_lines:
            lines.extend(["", "<b>По тарифам</b>"])
            lines.extend(plan_lines)

        currency_lines = self._currency_lines(stats.get("payments_by_currency", {}))
        if currency_lines:
            lines.extend(["", "<b>По валютам</b>"])
            lines.extend(currency_lines)

        if stats.get("legacy_pairs_only"):
            lines.extend([
                "",
                "<i>Детализация по суммам доступна для новых оплат. "
                "Количество пар включает ранее оплаченные подписки.</i>",
            ])
        elif not stats.get("has_detailed_payments") and paid_pairs == 0:
            lines.extend([
                "",
                "<i>За выбранный период оплат пока нет.</i>",
            ])

        gifted_pairs = stats.get("gifted_pairs", 0)
        if gifted_pairs:
            lines.extend([
                "",
                f"🎁 <b>Подарено админом</b>: <b>{gifted_pairs}</b> "
                f"{'пара' if gifted_pairs == 1 else 'пар'}",
            ])
            gift_lines = self._plan_lines(stats.get("gifted_by_plan", {}))
            lines.extend(gift_lines)

        return "\n".join(lines)

    def _plan_lines(self, data: dict[str, int], prefix: str = "  •") -> list[str]:
        result = []
        for plan_id in ("1_month", "3_months", "6_months", "1_year", "lifetime"):
            count = data.get(plan_id, 0)
            if count:
                result.append(
                    f"{prefix} {_PLAN_LABELS[plan_id]}: <b>{count}</b> "
                    f"{'пара' if count == 1 else 'пар'}"
                )
        return result

    def _format_amount(self, amount: Decimal, currency_code: str) -> str:
        info = SUPPORTED_CURRENCIES.get(currency_code, SUPPORTED_CURRENCIES["RUB"])
        decimals = info["decimals"]
        symbol = info["symbol"]
        normalized = amount.quantize(Decimal("1").scaleb(-decimals))
        value = f"{normalized:,.{decimals}f}".replace(",", " ")
        if symbol in ("₽", "€", "$"):
            return f"{value} {symbol}"
        return f"{value} {currency_code}"

    def _currency_lines(
        self,
        data: dict[str, dict[str, Decimal | int]],
    ) -> list[str]:
        result = []
        for currency_code in sorted(data.keys()):
            entry = data[currency_code]
            pair_count = int(entry.get("pairs", 0))
            revenue = Decimal(entry.get("revenue", 0))
            if not pair_count:
                continue
            amount_text = self._format_amount(revenue, currency_code)
            result.append(
                f"  • {currency_code}: <b>{pair_count}</b> "
                f"{'пара' if pair_count == 1 else 'пар'} · {amount_text}"
            )
        return result
