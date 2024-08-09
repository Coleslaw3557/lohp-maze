import logging
import math

logger = logging.getLogger(__name__)

def create_photobomb_bg_effect():
    photobomb_bg_effect = {
        "duration": 10.0,
        "description": "Background effect for the Photo Bomb room with subtle color changes",
        "steps": []
    }
    
    num_steps = 200  # 20 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (10.0 / num_steps)
        progress = i / num_steps
        
        # Subtle color changes
        hue = (math.sin(progress * 2 * math.pi) + 1) / 4 + 0.5  # Oscillate between 0.5 and 0.75 (cyan to blue)
        r, g, b = hsv_to_rgb(hue, 0.7, 0.6)  # Reduced saturation and value for subtlety
        
        photobomb_bg_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * 0.6),  # Constant moderate brightness
                "r_dimming": int(r * 255),
                "g_dimming": int(g * 255),
                "b_dimming": int(b * 255),
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Photo Bomb Background effect: {photobomb_bg_effect}")
    logger.info(f"Photo Bomb Background effect created with {len(photobomb_bg_effect['steps'])} steps over {photobomb_bg_effect['duration']} seconds")
    return photobomb_bg_effect

def hsv_to_rgb(h, s, v):
    if s == 0.0:
        return (v, v, v)
    i = int(h * 6.)
    f = (h * 6.) - i
    p, q, t = v * (1. - s), v * (1. - s * f), v * (1. - s * (1. - f))
    i %= 6
    if i == 0:
        return (v, t, p)
    if i == 1:
        return (q, v, p)
    if i == 2:
        return (p, v, t)
    if i == 3:
        return (p, q, v)
    if i == 4:
        return (t, p, v)
    if i == 5:
        return (v, p, q)
