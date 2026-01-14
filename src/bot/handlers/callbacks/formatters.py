"""Message formatting utilities."""


def format_caption_with_nickname(
    caption: str,
    pair,
    sender_user_id: int,
    pairs_repo,
) -> str:
    """Format caption with partner nickname at the beginning.
    
    Args:
        caption: Original caption text
        pair: Pair object
        sender_user_id: User ID of the sender (to determine which nickname to use)
        pairs_repo: PairsRepository instance
        
    Returns:
        Formatted caption with nickname prefix
    """
    # Get partner nickname (how recipient calls sender)
    partner_nickname = pairs_repo.get_partner_nickname(pair, sender_user_id)
    
    if partner_nickname:
        # Add nickname at the beginning: "от мама. Доброе утро!"
        return f"от {partner_nickname}. {caption}"
    else:
        # No nickname set, return original caption
        return caption


def format_confirmation_message(partner_nicknames: list[str]) -> str:
    """Format confirmation message with partner nicknames.
    
    Args:
        partner_nicknames: List of partner nicknames
        
    Returns:
        Formatted confirmation message
    """
    if len(partner_nicknames) == 1:
        return f"✅ Вы отправили пожелание {partner_nicknames[0]}"
    elif len(partner_nicknames) == 2:
        return f"✅ Вы отправили пожелание {partner_nicknames[0]} и {partner_nicknames[1]}"
    else:
        # For 3+ partners: "никнейм1, никнейм2 и никнейм3"
        last_nickname = partner_nicknames[-1]
        other_nicknames = ", ".join(partner_nicknames[:-1])
        return f"✅ Вы отправили пожелание {other_nicknames} и {last_nickname}"

