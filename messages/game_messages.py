def msg_pack_not_found() -> str:
    return "Пак не найден"


def msg_current_scores(score_lines: list[str]) -> str:
    return f"📈 Счёт:\n" + "\n".join(score_lines)


def msg_pack_info(pack_info: str) -> str:
    return f"📦 <b>Информация о паке:</b>\n\n{pack_info}"


def msg_themes_list(theme_names: list[str]) -> str:
    """Format a list of themes that will be played in the game."""
    return f"📋 <b>Темы игры:</b>\n\n" + "\n".join(theme_names)


def msg_theme_name(theme_name: str, comment: str = '') -> str:
    if comment:
        return f"📚 <b>{theme_name}</b>\n\n<b>Комментарий:</b> {comment}"
    return f"📚 <b>{theme_name}</b>"


def msg_attention_question() -> str:
    return "🔔 Внимание, вопрос!"


def msg_question(cost: int, theme_name: str, question_text: str) -> str:
    return f"<b>{cost}. {theme_name}</b>\n\n{question_text}"


def msg_question_partial(cost: int, theme_name: str, question_text: str, is_final: bool = False) -> str:
    """Format a partial question display with a typing cursor effect."""
    cursor: str = "" if is_final else " ▌"
    return f"<b>{cost}. {theme_name}</b>\n\n{question_text}{cursor}"


def msg_answer(answer: str, comment: str | None = None) -> str:
    message = f"<b>Ответ:</b> {answer}"
    if comment:
        message += f"\n\n<b>Комментарий:</b> {comment}"
    return message


def msg_game_over() -> str:
    return "🏆 Игра окончена!"


def msg_players_kick_warning() -> str:
    return "⏱️ Через 1 минуту все игроки будут удалены из игрового чата."


def msg_error(error: str) -> str:
    return f"Ошибка: {error}"


def msg_all_players_joined() -> str:
    return "🎮 Все игроки в сборе! Игра начинается!"


def msg_game_cancelled_inactivity() -> str:
    return "Игра отменена из-за неактивности."


def msg_time_up(player_name: str) -> str:
    return f"Время вышло! {player_name} не успел ответить."


def msg_player_answering(player_name: str) -> str:
    return f"{player_name} отвечает..."


def msg_question_hidden(cost: int, form: str) -> str:
    if form == '':
        form = 'Вопрос скрыт - игрок отвечает...'
    else:
        form = '<b>Форма: </b>' + form.upper()
    return f"❓ <b>{cost}</b>\n\n<i>{form.upper()}</i>"


def msg_correct_answer(player_name: str) -> str:
    return f"{player_name} ответил правильно"


def msg_incorrect_answer(player_name: str) -> str:
    return f"{player_name} ответил неправильно"


def msg_answer_confirmed(player_name: str) -> str:
    return f"Принято, {player_name}"
