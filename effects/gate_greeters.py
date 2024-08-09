import logging

logger = logging.getLogger(__name__)

def create_gate_greeters_effect():
    gate_greeters_effect = {
        "duration": 10.0,
        "description": "Welcoming effect with gentle color transitions and pulsing",
        "steps": []
    }
    
    # Generate steps for a smooth transition over 10 seconds
    num_steps = 100
    for i in range(num_steps + 1):
        t = i * (10.0 / num_steps)
        progress = i / num_steps
        
        # Gentle sine wave for pulsing effect
        pulse = (math.sin(progress * 2 * math.pi) + 1) / 2
        
        # Color transition from warm white to soft yellow
        r = int(255 * (0.8 + 0.2 * pulse))
        g = int(220 * (0.8 + 0.2 * pulse))
        b = int(180 * (0.8 + 0.2 * pulse))
        
        gate_greeters_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * (0.7 + 0.3 * pulse)),
                "r_dimming": r,
                "g_dimming": g,
                "b_dimming": b,
                "w_dimming": int(200 * (0.8 + 0.2 * pulse)),
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Gate Greeters effect: {gate_greeters_effect}")
    logger.info(f"Gate Greeters effect created with {len(gate_greeters_effect['steps'])} steps over {gate_greeters_effect['duration']} seconds")
    return gate_greeters_effect
