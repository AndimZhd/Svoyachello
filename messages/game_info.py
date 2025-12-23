def build_game_info_message(
    pack_name: str | None,
    number_of_themes: int,
    players: list[dict],
) -> str:
    pack_display = pack_name or "Случайный"
    
    if players:
        players_list = "\n".join(
            f"   • {p['username'] or 'Игрок'} ({p['elo_rating']})"
            for p in players
        )
    else:
        players_list = "   Пока никого нет"

    return (
        f"🎮 <b>Информация об игре</b>\n"
        f"{'━' * 20}\n\n"
        f"📦 <b>Пак:</b> {pack_display}\n"
        f"📋 <b>Темы:</b> {number_of_themes}\n\n"
        f"👥 <b>Игроки ({len(players)}):</b>\n"
        f"{players_list}"
    )

