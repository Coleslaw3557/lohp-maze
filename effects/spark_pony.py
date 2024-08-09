import logging
import random
import math

logger = logging.getLogger(__name__)

def create_spark_pony_effect():
    spark_pony_effect = {
        "duration": 10.0,
        "description": "Sparkling effect simulating a 'sparkle pony' with rapid color changes and brightness fluctuations",
        "steps": []
    }
    
    num_steps = 200  # 20 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (10.0 / num_steps)
        progress = i / num_steps
        
        # Rapid color changes
        hue = (math.sin(progress * 10 * math.pi) + 1) / 2
        r, g, b = hsv_to_rgb(hue, 1, 1)
        
        # Brightness fluctuations
        brightness = random.uniform(0.5, 1.0)
        
        # Occasional "sparkles"
        if random.random() < 0.1:  # 10% chance of a sparkle
            brightness = 1.0
            r, g, b = 255, 255, 255  # White sparkle
        
        spark_pony_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * brightness),
                "r_dimming": int(r * 255 * brightness),
                "g_dimming": int(g * 255 * brightness),
                "b_dimming": int(b * 255 * brightness),
                "w_dimming": int(255 * brightness) if random.random() < 0.05 else 0,  # Occasional white flash
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Spark Pony effect: {spark_pony_effect}")
    logger.info(f"Spark Pony effect created with {len(spark_pony_effect['steps'])} steps over {spark_pony_effect['duration']} seconds")
    return spark_pony_effect

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
