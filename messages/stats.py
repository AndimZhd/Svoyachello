def build_stats_message(
    display_name: str,
    row: dict,
) -> str:
    """Build user statistics message."""
    # Calculate accuracy
    total_answers = row['correct_answers'] + row['wrong_answers']
    accuracy = (row['correct_answers'] / total_answers * 100) if total_answers > 0 else 0

    return (
        f"📊 <b>Статистика игрока</b>\n"
        f"{'━' * 20}\n"
        f"👤 {display_name}\n\n"
        f"🏆 <b>Рейтинг:</b> {row['elo_rating']} ELO\n\n"
        f"🎮 <b>Игры:</b>\n"
        f"   • Сыграно: {row['games_played']}\n"
        f"   • Побед: {row['games_won']} ({row['win_percentage']:.1f}%)\n\n"
        f"💡 <b>Ответы:</b>\n"
        f"   • Правильных: {row['correct_answers']}\n"
        f"   • Неправильных: {row['wrong_answers']}\n"
        f"   • Точность: {accuracy:.1f}%\n\n"
        f"💰 <b>Очки:</b>\n"
        f"   • Всего заработано: {row['total_points_earned']}\n"
        f"   • Лучшая игра: {row['highest_game_score']}\n"
        f"   • Средний счёт: {row['average_game_score']}\n\n"
        f"🔥 <b>Серия побед:</b> {row['current_win_streak']} (рекорд: {row['best_win_streak']})"
    )

