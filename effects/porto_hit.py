import logging
import math

logger = logging.getLogger(__name__)

def create_porto_hit_effect():
    porto_hit_effect = {
        "duration": 3.0,
        "description": "Simulates a hit on the porto-potty with a quick flash and fade",
        "steps": []
    }
    
    num_steps = 60  # 20 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (3.0 / num_steps)
        progress = i / num_steps
        
        # Quick flash and fade
        intensity = math.exp(-5 * progress)  # Exponential decay
        
        porto_hit_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * intensity),
                "r_dimming": int(255 * intensity),
                "g_dimming": int(255 * intensity),
                "b_dimming": int(255 * intensity),
                "w_dimming": int(255 * intensity),
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Porto Hit effect: {porto_hit_effect}")
    logger.info(f"Porto Hit effect created with {len(porto_hit_effect['steps'])} steps over {porto_hit_effect['duration']} seconds")
    return porto_hit_effect
