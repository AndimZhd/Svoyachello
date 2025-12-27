import asyncio
from uuid import UUID

from aiogram import Bot

from database import games, game_chats, packs, players, statistics
from game.types import GameStatus


async def kick_users_from_game_chat(bot: Bot, game_chat_id: int, user_telegram_ids: list[int]) -> None:
    """Kick (ban and unban) users from the game chat."""
    for telegram_id in user_telegram_ids:
        try:
            await bot.ban_chat_member(game_chat_id, telegram_id)
            await bot.unban_chat_member(game_chat_id, telegram_id)
        except Exception:
            pass


async def unban_kicked_players(bot: Bot, game_chat_id: int, kicked_player_ids: set[int]) -> None:
    """Unban players who were kicked during the game."""
    for kicked_id in kicked_player_ids:
        try:
            await bot.unban_chat_member(game_chat_id, kicked_id)
        except Exception:
            pass


async def revoke_invite_link(bot: Bot, game_chat_id: int, invite_link: str) -> None:
    """Revoke the game's invite link."""
    try:
        await bot.revoke_chat_invite_link(game_chat_id, invite_link)
    except Exception:
        pass


async def calculate_player_rankings(session, uuid_to_info: dict[str, dict]) -> tuple:
    """Calculate player scores, sort players, and determine winners."""
    scores = await games.get_game_scores(session.game_chat_id)
    
    player_scores: dict[UUID, int] = {}
    player_abs_scores: dict[UUID, int] = {}
    
    for player_uuid in session.players:
        uuid_str = str(player_uuid)
        player_scores[player_uuid] = int(scores.get(uuid_str, 0))
        
        if session.player_abs_scores:
            player_abs_scores[player_uuid] = session.player_abs_scores.get(player_uuid, 0)
        else:
            player_abs_scores[player_uuid] = 0
    
    sorted_players = sorted(
        session.players,
        key=lambda pid: (player_scores.get(pid, 0), player_abs_scores.get(pid, 0)),
        reverse=True
    )
    
    num_winners = max(1, len(session.players) // 2)
    winners = set(sorted_players[:num_winners])
    
    return player_scores, sorted_players, winners


async def get_player_ratings(player_uuids: list[UUID]) -> dict[UUID, int]:
    """Get or create ELO ratings for players."""
    player_ratings: dict[UUID, int] = {}
    
    for player_uuid in player_uuids:
        stats = await statistics.get_statistics_by_player_id(player_uuid)
        if stats:
            player_ratings[player_uuid] = stats.get('elo_rating', 1000)
        else:
            await statistics.create_statistics(player_uuid)
            player_ratings[player_uuid] = 1000
    
    return player_ratings


async def update_player_statistics(session, player_scores: dict[UUID, int], winners: set[UUID], 
                                   player_ratings: dict[UUID, int], elo_changes: dict[UUID, int],
                                   uuid_to_info: dict[str, dict]) -> None:
    """Update game statistics for all players."""
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


async def send_game_results(bot: Bot, session, sorted_players: list[UUID], 
                          player_scores: dict[UUID, int], player_ratings: dict[UUID, int],
                          elo_changes: dict[UUID, int], uuid_to_info: dict[str, dict]) -> None:
    """Send game results to game chat and origin chat."""
    import messages
    
    result_lines = []
    
    for player_uuid in sorted_players:
        info = uuid_to_info.get(str(player_uuid), {})
        first = info.get('first_name') or ''
        last = info.get('last_name') or ''
        name = f"{first} {last}".strip() or info.get('username') or 'Игрок'
        score = player_scores.get(player_uuid, 0)
        elo_change = elo_changes.get(player_uuid, 0)
        new_elo = player_ratings.get(player_uuid, 1000) + elo_change
        
        elo_str = f"+{elo_change}" if elo_change >= 0 else str(elo_change)
        result_lines.append(f"{name}: {score} очков ({new_elo} {elo_str})")
    
    results_message = "📊 <b>Итоги игры:</b>\n\n" + "\n".join(result_lines)
    
    await bot.send_message(session.game_chat_id, results_message, parse_mode="HTML")

    await bot.send_message(session.game_chat_id, messages.msg_players_kick_warning())
    
    if session.origin_chat_id != session.game_chat_id:
        try:
            await bot.send_message(session.origin_chat_id, results_message, parse_mode="HTML")
        except Exception:
            pass


async def update_pack_history(session, pack_id: UUID, user_uuids: list[UUID], up_to_current: bool = False) -> None:
    """Update pack history for players or spectators."""
    for user_uuid in user_uuids:
        start_idx = 0
        if session.player_start_theme_idx:
            start_idx = session.player_start_theme_idx.get(user_uuid, 0)
        
        if up_to_current:
            end_idx = session.current_theme_idx
            if session.current_question_idx > 0:
                end_idx = session.current_theme_idx + 1
            
            if start_idx < end_idx:
                user_themes = session.pack_themes[start_idx:end_idx]
            else:
                user_themes = []
        else:
            user_themes = session.pack_themes[start_idx:]
        
        if user_themes:
            print(f"[PACK HISTORY] Player {user_uuid}: pack={pack_id}, themes={user_themes}, start_idx={start_idx}, up_to_current={up_to_current}")
            await packs.update_player_pack_history(user_uuid, pack_id, user_themes)
        else:
            print(f"[PACK HISTORY] Player {user_uuid}: no themes to save, start_idx={start_idx}, up_to_current={up_to_current}")


async def cleanup_game(game_id: UUID, game_chat_id: int) -> None:
    """Release game chat and delete game from database."""
    await game_chats.release_game_chat(game_id)
    await games.delete_game(game_chat_id)


async def finalize_game(chat_id: int, bot: Bot, is_aborted: bool = False) -> None:
    """Finalize a game session: update statistics, send results, and cleanup."""
    from .sessions import session_manager
    
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        return
    
    if game['status'] == GameStatus.REGISTERED.value:
        await cleanup_game(game['id'], chat_id)
        return
    
    session = session_manager.get(chat_id)
    if not session:
        await cleanup_game(game['id'], chat_id)
        return
    
    game_chat_id = session.game_chat_id

    if session.invite_link:
        await revoke_invite_link(bot, game_chat_id, session.invite_link)

    players_info = await players.get_players_telegram_ids(session.players)
    player_telegram_ids = [info['telegram_id'] for info in players_info if info.get('telegram_id')]
    
    spectator_telegram_ids = []
    if session.spectators:
        spectators_info = await players.get_players_telegram_ids(session.spectators)
        spectator_telegram_ids = [info['telegram_id'] for info in spectators_info if info.get('telegram_id')]
    
    if is_aborted:
        pack = await packs.get_pack_by_short_name(game['pack_short_name'])
        if pack:
            await update_pack_history(session, pack['id'], session.players, up_to_current=True)
            
            if session.spectators:
                await update_pack_history(session, pack['id'], session.spectators, up_to_current=True)

        await asyncio.sleep(20)

        await kick_users_from_game_chat(bot, game_chat_id, player_telegram_ids)
        await kick_users_from_game_chat(bot, game_chat_id, spectator_telegram_ids)
        
        if session.kicked_players:
            await unban_kicked_players(bot, game_chat_id, session.kicked_players)
        
        await cleanup_game(game['id'], game_chat_id)
        await session_manager.stop(chat_id)
        return
    
    uuid_to_info: dict[str, dict] = {str(info['id']): info for info in players_info}
    
    player_scores, sorted_players, winners = await calculate_player_rankings(session, uuid_to_info)
    
    player_ratings = await get_player_ratings(session.players)
    
    elo_changes: dict[UUID, int] = {player_uuid: 0 for player_uuid in session.players}
    if len(session.players) >= 2:
        elo_changes = statistics.calculate_elo_changes(player_ratings, player_scores)
    
    await update_player_statistics(session, player_scores, winners, player_ratings, elo_changes, uuid_to_info)
    
    for player_uuid in session.players:
        await players.track_player_in_chat(player_uuid, session.origin_chat_id)
    
    await send_game_results(bot, session, sorted_players, player_scores, player_ratings, elo_changes, uuid_to_info)
    
    pack = await packs.get_pack_by_short_name(game['pack_short_name'])
    if pack:
        await update_pack_history(session, pack['id'], session.players)
        
        if session.spectators:
            await update_pack_history(session, pack['id'], session.spectators)

    await asyncio.sleep(60)
    
    await kick_users_from_game_chat(bot, game_chat_id, player_telegram_ids)
    await kick_users_from_game_chat(bot, game_chat_id, spectator_telegram_ids)
    
    if session.kicked_players:
        await unban_kicked_players(bot, game_chat_id, session.kicked_players)
    
    await cleanup_game(game['id'], game_chat_id)
    
    await session_manager.stop(chat_id)
