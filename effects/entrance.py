import logging
import math

logger = logging.getLogger(__name__)

def create_entrance_effect():
    entrance_effect = {
        "duration": 15.0,
        "description": "Welcoming effect with warm colors and gentle pulsing for the entrance",
        "steps": []
    }
    
    num_steps = 150  # 10 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (15.0 / num_steps)
        progress = i / num_steps
        
        # Gentle sine wave for pulsing effect
        pulse = (math.sin(progress * 2 * math.pi) + 1) / 2
        
        # Warm color palette transitioning from orange to yellow
        r = int(255 * (0.9 + 0.1 * pulse))
        g = int((180 + 75 * progress) * (0.8 + 0.2 * pulse))
        b = int(50 * (0.7 + 0.3 * pulse))
        
        entrance_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * (0.7 + 0.3 * pulse)),
                "r_dimming": r,
                "g_dimming": g,
                "b_dimming": b,
                "w_dimming": int(100 * (0.8 + 0.2 * pulse)),
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Entrance effect: {entrance_effect}")
    logger.info(f"Entrance effect created with {len(entrance_effect['steps'])} steps over {entrance_effect['duration']} seconds")
    return entrance_effect
