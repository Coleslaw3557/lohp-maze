import logging
import math

logger = logging.getLogger(__name__)

def create_porto_standby_effect():
    porto_standby_effect = {
        "duration": 10.0,
        "description": "Gentle pulsing blue light for Porto Room standby state",
        "steps": []
    }
    
    num_steps = 100  # 10 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (10.0 / num_steps)
        progress = i / num_steps
        
        # Gentle sine wave for pulsing effect
        pulse = (math.sin(progress * 2 * math.pi) + 1) / 2
        
        # Blue color with slight variation
        b = int(200 + 55 * pulse)
        
        porto_standby_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * (0.6 + 0.4 * pulse)),
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": b,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Porto Standby effect: {porto_standby_effect}")
    logger.info(f"Porto Standby effect created with {len(porto_standby_effect['steps'])} steps over {porto_standby_effect['duration']} seconds")
    return porto_standby_effect
