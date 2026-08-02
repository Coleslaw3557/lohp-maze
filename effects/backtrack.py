import logging

logger = logging.getLogger(__name__)


def create_backtrack_effect():
    effect = {
        "duration": 2.4,
        "description": "Red and amber warning flashes for reverse maze travel",
        "steps": [
            {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 20, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.18, "channels": {"total_dimming": 30, "r_dimming": 255, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.36, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 130, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.54, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.78, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 180, "function_selection": 0, "function_speed": 0}},
            {"time": 1.18, "channels": {"total_dimming": 160, "r_dimming": 255, "g_dimming": 80, "b_dimming": 0, "w_dimming": 0, "total_strobe": 120, "function_selection": 0, "function_speed": 0}},
            {"time": 1.62, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 60, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.92, "channels": {"total_dimming": 80, "r_dimming": 255, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 2.4, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
        ],
    }
    logger.info(f"Backtrack effect created with {len(effect['steps'])} steps over {effect['duration']} seconds")
    return effect
