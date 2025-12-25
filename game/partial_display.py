"""
Utility functions for displaying questions in parts/stages.
"""
from typing import List


def split_question_into_parts(question_text: str, num_parts: int = 10, min_part_length: int = 40) -> List[str]:
    """
    Split a question into parts for progressive display based on length.
    
    Args:
        question_text: The full question text
        num_parts: Number of parts to split into (default: 10)
        min_part_length: Minimum length for each part in characters (default: 10)
    
    Returns:
        List of question parts, each progressively longer
    """
    if not question_text:
        return [""]
    
    total_length = len(question_text)
    
    # If question is too short for the requested number of parts, reduce parts
    if total_length < min_part_length * num_parts:
        # Calculate how many parts we can actually make
        num_parts = max(1, total_length // min_part_length)
    
    # If we can only make 1 part, return the whole question
    if num_parts == 1:
        return [question_text]
    
    # Calculate the length increment for each part
    part_length_increment = total_length // num_parts
    
    # Make sure increment is at least min_part_length
    if part_length_increment < min_part_length:
        part_length_increment = min_part_length
        num_parts = max(1, total_length // part_length_increment)
    
    parts = []
    for i in range(1, num_parts + 1):
        # Calculate how much of the question to show
        end_index = min(i * part_length_increment, total_length)
        
        # For the last part, always show the complete question
        if i == num_parts:
            end_index = total_length
        
        part_text = question_text[:end_index]
        parts.append(part_text)
    
    return parts


def should_display_partially(question_text: str, threshold_length: int = 30) -> bool:
    """
    Determine if a question should be displayed in parts.
    
    Args:
        question_text: The question text
        threshold_length: Minimum length to consider partial display (default: 100)
    
    Returns:
        True if question should be displayed in parts
    """
    if not question_text:
        return False
    
    return len(question_text) > threshold_length

