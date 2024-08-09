import logging

logger = logging.getLogger(__name__)

def create_correct_answer_effect():
    correct_answer_effect = {
        "duration": 2.0,
        "description": "Three quick green flashes to indicate a correct answer",
        "steps": []
    }
    
    for i in range(3):
        t = i * 0.5
        correct_answer_effect["steps"].extend([
            {"time": t, "channels": {"total_dimming": 255, "r_dimming": 0, "g_dimming": 255, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": t + 0.25, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ])
    
    logger.debug(f"Created Correct Answer effect: {correct_answer_effect}")
    logger.info(f"Correct Answer effect created with {len(correct_answer_effect['steps'])} steps over {correct_answer_effect['duration']} seconds")
    return correct_answer_effect
