"""
Utility functions for displaying questions in parts/stages.
"""
from typing import List


_MAX_FRAMES: int = 15
_WORDS_PER_FRAME: int = 6


def split_question_into_parts(
    question_text: str,
    words_per_frame: int = _WORDS_PER_FRAME,
    max_frames: int = _MAX_FRAMES,
) -> List[str]:
    """
    Split a question into progressively longer frames for streaming display.

    Each frame adds a batch of words to the previous one, so text is never
    broken mid-word.  The number of frames adapts to the question length.

    Args:
        question_text: The full question text.
        words_per_frame: How many words each new frame adds (default: 6).
        max_frames: Upper bound on the number of frames (default: 15).

    Returns:
        List of cumulative text frames (the last one is always the full text).
    """
    if not question_text:
        return [question_text or ""]

    words: List[str] = question_text.split()
    total_words: int = len(words)

    if total_words <= words_per_frame:
        return [question_text]

    raw_frames: int = (total_words + words_per_frame - 1) // words_per_frame
    num_frames: int = min(raw_frames, max_frames)

    # Recalculate batch size so words are evenly distributed across frames
    batch: int = max(1, total_words // num_frames)

    frames: List[str] = []
    for i in range(1, num_frames + 1):
        end: int = min(i * batch, total_words)
        if i == num_frames:
            end = total_words
        frames.append(" ".join(words[:end]))

    return frames


def should_display_partially(question_text: str, threshold_length: int = 30) -> bool:
    """
    Determine if a question should be displayed in parts.

    Args:
        question_text: The question text.
        threshold_length: Minimum character length to consider partial
            display (default: 30).

    Returns:
        True if question should be displayed in parts.
    """
    if not question_text:
        return False

    return len(question_text) > threshold_length
