def msg_pack_not_found() -> str:
    return "❌ Ошибка: пак не найден"


def msg_score_summary(score_messages: list[str]) -> str:
    return f"📊 Итог: {', '.join(score_messages)}"


def msg_current_scores(score_lines: list[str]) -> str:
    return f"📈 Счёт:\n" + "\n".join(score_lines)


def msg_pack_info(pack_info: str) -> str:
    return f"📦 <b>Информация о паке:</b>\n\n{pack_info}"


def msg_theme_name(theme_name: str) -> str:
    return f"📚 <b>{theme_name}</b>"


def msg_attention_question() -> str:
    return "🔔 Внимание, вопрос!"


def msg_question(cost: int, theme_name: str, question_text: str) -> str:
    return f"<b>{cost}. {theme_name}</b>\n\n{question_text}"


def msg_answer(answer: str, comment: str | None = None) -> str:
    message = f"Ответ: {answer}"
    if comment:
        message += f"\n\nКомментарий: {comment}"
    return message


def msg_score_correction() -> str:
    return "⚖️ Коррекция очков: /yes если правильно, /no если неправильно (5 сек)"


def msg_game_over() -> str:
    return "🏆 Игра окончена!"


def msg_error(error: str) -> str:
    return f"❌ Ошибка: {error}"


def msg_all_players_joined() -> str:
    return "🎮 Все игроки в сборе! Игра начинается!"


def msg_game_cancelled_inactivity() -> str:
    return "Игра отменена из-за неактивности."


def msg_time_up(player_name: str) -> str:
    return f"⏱ Время вышло! @{player_name} не успел ответить."


def msg_player_answering(player_name: str) -> str:
    return f"🎯 @{player_name} отвечает! У вас 10 секунд..."


def msg_question_hidden(cost: int) -> str:
    return f"❓ <b>{cost}</b>\n\n<i>Вопрос скрыт - игрок отвечает...</i>"


def msg_someone_answering() -> str:
    return "Кто-то уже отвечает!"


def msg_correct_answer(player_name: str) -> str:
    return f"✅ @{player_name} ответил правильно!"


def msg_incorrect_answer(player_name: str) -> str:
    return f"❌ @{player_name} ответил неправильно!"


def msg_question_claimed() -> str:
    return "Вопрос уже засчитан другому игроку!"


def msg_answer_already_correct() -> str:
    return "Ваш ответ уже засчитан как правильный!"


def msg_answer_confirmed(player_name: str) -> str:
    return f"✅ @{player_name}: ответ засчитан!"


def msg_answer_already_incorrect() -> str:
    return "Ваш ответ уже засчитан как неправильный!"


def msg_answer_rejected(player_name: str) -> str:
    return f"❌ @{player_name}: ответ не засчитан!"


def msg_answer_already_accidental() -> str:
    return "Ваш ответ уже помечен как случайный!"


def msg_answer_marked_accidental(player_name: str) -> str:
    return f"🙈 @{player_name}: ответ помечен как случайный!"

