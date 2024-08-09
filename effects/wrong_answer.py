import logging

logger = logging.getLogger(__name__)

def create_wrong_answer_effect():
    wrong_answer_effect = {
        "duration": 1.5,
        "description": "Three quick red flashes to indicate a wrong answer",
        "steps": []
    }
    
    for i in range(3):
        t = i * 0.5
        wrong_answer_effect["steps"].extend([
            {"time": t, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": t + 0.25, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ])
    
    logger.debug(f"Created Wrong Answer effect: {wrong_answer_effect}")
    logger.info(f"Wrong Answer effect created with {len(wrong_answer_effect['steps'])} steps over {wrong_answer_effect['duration']} seconds")
    return wrong_answer_effect
