import logging
import math

logger = logging.getLogger(__name__)

def create_image_enhancement_effect():
    image_enhancement_effect = {
        "duration": 18.0,  # 3 seconds fade up + 15 seconds full brightness
        "description": "3-second fade up to orange, then 15 seconds at full brightness for image enhancement effect",
        "audio_file": "image-enhancement.mp3",
        "steps": []
    }
    
    fade_duration = 3.0
    full_brightness_duration = 15.0
    num_steps = 180  # 10 steps per second for smooth transition
    
    # Fade up to orange over 3 seconds
    for i in range(int(fade_duration * 10) + 1):
        t = i * (fade_duration / (fade_duration * 10))
        progress = i / (fade_duration * 10)
        
        # Linear fade up
        intensity = progress
        
        # Orange color
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
    
    # Maintain full brightness for 15 seconds
    full_brightness_steps = int(full_brightness_duration * 10)
    for i in range(full_brightness_steps + 1):
        t = fade_duration + i * (full_brightness_duration / full_brightness_steps)
        
        image_enhancement_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 255,
                "g_dimming": 165,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Image Enhancement effect: {image_enhancement_effect}")
    logger.info(f"Image Enhancement effect created with {len(image_enhancement_effect['steps'])} steps over {image_enhancement_effect['duration']} seconds")
    return image_enhancement_effect
