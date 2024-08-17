import logging

logger = logging.getLogger(__name__)

def create_no_friends_monday_effect():
    no_friends_monday_effect = {
        "duration": 5.0,
        "description": "Bright white light for No Friends Monday",
        "steps": [
            {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 191, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 5.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ]
    }
    logger.debug(f"Created NoFriendsMonday effect: {no_friends_monday_effect}")
    logger.info(f"NoFriendsMonday effect created with {len(no_friends_monday_effect['steps'])} steps over {no_friends_monday_effect['duration']} seconds")
    return no_friends_monday_effect
