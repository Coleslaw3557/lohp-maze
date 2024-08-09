import logging
import math

logger = logging.getLogger(__name__)

def create_guy_line_climb_effect():
    guy_line_climb_effect = {
        "duration": 15.0,
        "description": "Simulates climbing vines in a jungle with blues and greens and a low strobe, lasting 15 seconds",
        "steps": []
    }
    
    num_steps = 150  # 10 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (15.0 / num_steps)
        progress = i / num_steps
        
        # Sine wave for pulsing effect
        pulse = (math.sin(progress * 2 * math.pi * 2) + 1) / 2  # Faster pulse
        
        # Color transition from blue to green
        r = 0
        g = int(128 + 127 * math.sin(progress * math.pi))
        b = int(255 - 127 * math.sin(progress * math.pi))
        
        # Low strobe effect
        strobe = int(64 + 63 * math.sin(progress * 2 * math.pi * 4))  # Faster strobe
        
        guy_line_climb_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * (0.7 + 0.3 * pulse)),
                "r_dimming": r,
                "g_dimming": g,
                "b_dimming": b,
                "w_dimming": 0,
                "total_strobe": strobe,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Guy Line Climb effect: {guy_line_climb_effect}")
    logger.info(f"Guy Line Climb effect created with {len(guy_line_climb_effect['steps'])} steps over {guy_line_climb_effect['duration']} seconds")
    return guy_line_climb_effect
