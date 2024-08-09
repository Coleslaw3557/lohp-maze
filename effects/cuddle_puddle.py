import logging
import math

logger = logging.getLogger(__name__)

def create_cuddle_puddle_effect():
    cuddle_puddle_effect = {
        "duration": 20.0,
        "description": "Soft, warm, and inviting light effect for the Cuddle Puddle area",
        "steps": []
    }
    
    num_steps = 200  # 10 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (20.0 / num_steps)
        progress = i / num_steps
        
        # Gentle sine wave for pulsing effect
        pulse = (math.sin(progress * 2 * math.pi) + 1) / 2
        
        # Warm, soft colors transitioning between pink, orange, and yellow
        r = int(255 * (0.8 + 0.2 * pulse))
        g = int((180 + 75 * math.sin(progress * math.pi)) * (0.7 + 0.3 * pulse))
        b = int((100 + 50 * math.sin(progress * 1.5 * math.pi)) * (0.6 + 0.4 * pulse))
        
        cuddle_puddle_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * (0.6 + 0.4 * pulse)),
                "r_dimming": r,
                "g_dimming": g,
                "b_dimming": b,
                "w_dimming": int(100 * (0.7 + 0.3 * pulse)),
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Cuddle Puddle effect: {cuddle_puddle_effect}")
    logger.info(f"Cuddle Puddle effect created with {len(cuddle_puddle_effect['steps'])} steps over {cuddle_puddle_effect['duration']} seconds")
    return cuddle_puddle_effect
