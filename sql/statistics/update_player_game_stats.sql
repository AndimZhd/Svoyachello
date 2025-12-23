-- Update player statistics after a game
-- $1: player_id (UUID)
-- $2: game_score (INTEGER) - player's final score in this game
-- $3: is_winner (BOOLEAN) - whether the player won
-- $4: correct_answers (INTEGER) - number of correct answers this game
-- $5: wrong_answers (INTEGER) - number of wrong answers this game
-- $6: elo_change (INTEGER) - ELO rating change

UPDATE statistics
SET
    games_played = games_played + 1,
    games_won = games_won + CASE WHEN $3 THEN 1 ELSE 0 END,
    win_percentage = CASE 
        WHEN games_played + 1 > 0 
        THEN (games_won + CASE WHEN $3 THEN 1 ELSE 0 END)::REAL / (games_played + 1)::REAL * 100
        ELSE 0 
    END,
    correct_answers = correct_answers + $4,
    wrong_answers = wrong_answers + $5,
    total_points_earned = total_points_earned + $2,
    highest_game_score = GREATEST(highest_game_score, $2),
    average_game_score = CASE
        WHEN games_played + 1 > 0
        THEN (total_points_earned + $2) / (games_played + 1)
        ELSE 0
    END,
    current_win_streak = CASE WHEN $3 THEN current_win_streak + 1 ELSE 0 END,
    best_win_streak = GREATEST(best_win_streak, CASE WHEN $3 THEN current_win_streak + 1 ELSE current_win_streak END),
    elo_rating = elo_rating + $6,
    last_played_at = NOW()
WHERE user_id = $1;

