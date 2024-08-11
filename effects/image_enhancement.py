import logging
import math

logger = logging.getLogger(__name__)

def create_image_enhancement_effect():
    image_enhancement_effect = {
        "duration": 15.0,
        "description": "Quick fade up to orange for image enhancement effect",
        "steps": []
    }
    
    num_steps = 150  # 10 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (15.0 / num_steps)
        progress = i / num_steps
        
        # Quick fade up
        intensity = math.pow(progress, 0.5)  # Use square root for quicker initial fade
        
        # Orange color (adjust these values to get the desired shade of orange)
        r = int(255 * intensity)
        g = int(165 * intensity)
        b = int(0 * intensity)
        
        image_enhancement_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * intensity),
                "r_dimming": r,
                "g_dimming": g,
                "b_dimming": b,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Image Enhancement effect: {image_enhancement_effect}")
    logger.info(f"Image Enhancement effect created with {len(image_enhancement_effect['steps'])} steps over {image_enhancement_effect['duration']} seconds")
    return image_enhancement_effect
