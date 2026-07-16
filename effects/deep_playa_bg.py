import logging
import math
from effect_utils import hsv_to_rgb

logger = logging.getLogger(__name__)

def create_deep_playa_bg_effect():
    deep_playa_bg_effect = {
        "duration": 20.0,
        "description": "Background effect for the Deep Playa area with subtle, slow-changing colors",
        "steps": []
    }
    
    num_steps = 200  # 10 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (20.0 / num_steps)
        progress = i / num_steps
        
        # Slow, subtle color changes
        hue = (math.sin(progress * math.pi) + 1) / 4 + 0.5  # Oscillate between 0.5 and 0.75 (cyan to blue)
        r, g, b = hsv_to_rgb(hue, 0.6, 0.4)  # Reduced saturation and value for subtlety
        
        deep_playa_bg_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * 0.4),  # Constant low brightness
                "r_dimming": int(r * 255),
                "g_dimming": int(g * 255),
                "b_dimming": int(b * 255),
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Deep Playa Background effect: {deep_playa_bg_effect}")
    logger.info(f"Deep Playa Background effect created with {len(deep_playa_bg_effect['steps'])} steps over {deep_playa_bg_effect['duration']} seconds")
    return deep_playa_bg_effect

