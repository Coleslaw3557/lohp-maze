import logging
import random

logger = logging.getLogger(__name__)

def create_bike_lock_room_effect():
    bike_lock_room_effect = {
        "duration": 10.0,
        "description": "Borg ship action scene effect for Bike Lock Room",
        "steps": []
    }
    
    # Colors: Green, Red, and Blue (Borg-like colors)
    colors = [
        {"r": 0, "g": 255, "b": 0},    # Green
        {"r": 255, "g": 0, "b": 0},    # Red
        {"r": 0, "g": 0, "b": 255},    # Blue
    ]
    
    step_duration = 0.1  # 100ms per step
    num_steps = int(bike_lock_room_effect["duration"] / step_duration)
    
    for i in range(num_steps):
        time = i * step_duration
        color = random.choice(colors)
        intensity = random.randint(100, 255)  # Random intensity for flickering effect
        
        step = {
            "time": time,
            "channels": {
                "total_dimming": intensity,
                "r_dimming": color["r"],
                "g_dimming": color["g"],
                "b_dimming": color["b"],
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        }
        bike_lock_room_effect["steps"].append(step)
    
    # Ensure the last step turns off the lights
    bike_lock_room_effect["steps"].append({
        "time": bike_lock_room_effect["duration"],
        "channels": {
            "total_dimming": 0,
            "r_dimming": 0,
            "g_dimming": 0,
            "b_dimming": 0,
            "w_dimming": 0,
            "total_strobe": 0,
            "function_selection": 0,
            "function_speed": 0
        }
    })
    
    logger.debug(f"Created BikeLockRoom effect: {bike_lock_room_effect}")
    logger.info(f"BikeLockRoom effect created with {len(bike_lock_room_effect['steps'])} steps over {bike_lock_room_effect['duration']} seconds")
    return bike_lock_room_effect
