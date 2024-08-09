import logging

logger = logging.getLogger(__name__)

def create_gate_inspection_effect():
    gate_inspection_effect = {
        "duration": 5.0,
        "description": "Bright white light for gate inspection, lasting 5 seconds",
        "steps": [
            {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 5.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ]
    }
    logger.debug(f"Created Gate Inspection effect: {gate_inspection_effect}")
    logger.info(f"Gate Inspection effect created with {len(gate_inspection_effect['steps'])} steps over {gate_inspection_effect['duration']} seconds")
    return gate_inspection_effect
