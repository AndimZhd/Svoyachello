-- Insert player rights or update if exists
INSERT INTO player_rights (
    player_id,
    can_abort,
    number_of_pauses,
    can_abort_all,
    can_correct,
    can_skip_theme
)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (player_id) DO UPDATE SET
    can_abort = EXCLUDED.can_abort,
    number_of_pauses = EXCLUDED.number_of_pauses,
    can_abort_all = EXCLUDED.can_abort_all,
    can_correct = EXCLUDED.can_correct,
    can_skip_theme = EXCLUDED.can_skip_theme
RETURNING *;

