from uuid import UUID

from aiogram import Bot

from database import games, game_chats, packs, players, statistics


async def finalize_game(session, bot: Bot) -> None:
    game_chat_id = session.game_chat_id
    
    scores = await games.get_game_scores(game_chat_id)
    
    game = await games.get_game_by_chat_id(game_chat_id)
    if not game:
        return
    
    players_info = await players.get_players_telegram_ids(session.players)
    uuid_to_info: dict[str, dict] = {}
    for info in players_info:
        uuid_to_info[str(info['id'])] = info
    
    player_scores: dict[UUID, int] = {}
    player_abs_scores: dict[UUID, int] = {}
    for player_uuid in session.players:
        uuid_str = str(player_uuid)
        player_scores[player_uuid] = int(scores.get(uuid_str, 0))
        
        info = uuid_to_info.get(uuid_str, {})
        telegram_id = info.get('telegram_id')
        if telegram_id and session.player_abs_scores:
            player_abs_scores[player_uuid] = session.player_abs_scores.get(telegram_id, 0)
        else:
            player_abs_scores[player_uuid] = 0
    
    sorted_players = sorted(
        session.players,
        key=lambda pid: (player_scores.get(pid, 0), player_abs_scores.get(pid, 0)),
        reverse=True
    )
    
    num_winners = max(1, len(session.players) // 2)
    winners = set(sorted_players[:num_winners])
    
    player_ratings: dict[UUID, int] = {}
    for player_uuid in session.players:
        stats = await statistics.get_statistics_by_player_id(player_uuid)
        if stats:
            player_ratings[player_uuid] = stats.get('elo_rating', 1000)
        else:
            await statistics.create_statistics(player_uuid)
            player_ratings[player_uuid] = 1000
    
    elo_changes: dict[UUID, int] = {player_uuid: 0 for player_uuid in session.players}
    
    if len(session.players) >= 2:
        elo_changes = statistics.calculate_elo_changes(player_ratings, player_scores)
        
        for player_uuid in session.players:
            is_winner = player_uuid in winners
            game_score = player_scores.get(player_uuid, 0)
            elo_change = elo_changes.get(player_uuid, 0)
            
            info = uuid_to_info.get(str(player_uuid), {})
            telegram_id = info.get('telegram_id')
            correct_answers = 0
            wrong_answers = 0
            if telegram_id:
                if session.player_correct_answers:
                    correct_answers = session.player_correct_answers.get(telegram_id, 0)
                if session.player_wrong_answers:
                    wrong_answers = session.player_wrong_answers.get(telegram_id, 0)
            
            await statistics.update_player_game_stats(
                player_id=player_uuid,
                game_score=game_score,
                is_winner=is_winner,
                correct_answers=correct_answers,
                wrong_answers=wrong_answers,
                elo_change=elo_change
            )
    
    for player_uuid in session.players:
        await players.track_player_in_chat(player_uuid, session.origin_chat_id)
    
    result_lines = []
    for i, player_uuid in enumerate(sorted_players):
        info = uuid_to_info.get(str(player_uuid), {})
        first = info.get('first_name') or ''
        last = info.get('last_name') or ''
        name = f"{first} {last}".strip() or info.get('username') or 'Игрок'
        score = player_scores.get(player_uuid, 0)
        elo_change = elo_changes.get(player_uuid, 0)
        new_elo = player_ratings.get(player_uuid, 1000) + elo_change
        
        elo_str = f"+{elo_change}" if elo_change >= 0 else str(elo_change)
        
        medal = ""
        if i == 0:
            medal = "🥇 "
        elif i == 1:
            medal = "🥈 "
        elif i == 2:
            medal = "🥉 "
        
        result_lines.append(f"{medal}{name}: {score} очков ({new_elo} {elo_str})")
    
    results_message = "📊 <b>Итоги игры:</b>\n\n" + "\n".join(result_lines)
    
    await bot.send_message(game_chat_id, results_message, parse_mode="HTML")
    
    if session.origin_chat_id != game_chat_id:
        try:
            await bot.send_message(session.origin_chat_id, results_message, parse_mode="HTML")
        except Exception:
            pass
    
    if session.invite_link:
        try:
            await bot.revoke_chat_invite_link(game_chat_id, session.invite_link)
        except Exception:
            pass
    
    for player_info in players_info:
        telegram_id = player_info.get('telegram_id')
        if telegram_id:
            try:
                await bot.ban_chat_member(game_chat_id, telegram_id)
                await bot.unban_chat_member(game_chat_id, telegram_id)
            except Exception:
                pass
    
    pack = await packs.get_pack_by_short_name(game['pack_short_name'])
    if pack:
        for player_uuid in session.players:
            start_idx = 0
            if session.player_start_theme_idx:
                start_idx = session.player_start_theme_idx.get(player_uuid, 0)
            
            player_themes = session.pack_themes[start_idx:]
            if player_themes:
                await packs.update_player_pack_history(player_uuid, pack['id'], player_themes)
    
    await game_chats.release_game_chat(game['id'])
    await games.delete_game(game_chat_id)

