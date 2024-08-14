import logging

logger = logging.getLogger(__name__)

def create_deep_playa_hit_effect():
    deep_playa_hit_effect = {
        "duration": 3.0,
        "description": "Amber flash for Deep Playa Hit",
        "steps": [
            {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 191, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.5, "channels": {"total_dimming": 0, "r_dimming": 255, "g_dimming": 191, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 191, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.5, "channels": {"total_dimming": 0, "r_dimming": 255, "g_dimming": 191, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 2.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 191, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 3.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ]
    }
    logger.debug(f"Created DeepPlaya-Hit effect: {deep_playa_hit_effect}")
    logger.info(f"DeepPlaya-Hit effect created with {len(deep_playa_hit_effect['steps'])} steps over {deep_playa_hit_effect['duration']} seconds")
    return deep_playa_hit_effect
