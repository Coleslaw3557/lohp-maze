import logging

logger = logging.getLogger(__name__)

def create_photobomb_spot_effect():
    photobomb_spot_effect = {
        "duration": 15.0,  # Duration of the "Girls on Film" intro
        "description": "Flashing white light for Photo Bomb Room, synced with 'Girls on Film'",
        "steps": []
    }
    
    # Define the beat timings (in seconds) based on the spectrogram
    beat_timings = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 
                    6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 
                    11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5]
    
    for i, time in enumerate(beat_timings):
        # On beat: bright white
        photobomb_spot_effect["steps"].append({
            "time": time,
            "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}
        })
        
        # Off beat: dim
        if i < len(beat_timings) - 1:
            off_time = (time + beat_timings[i+1]) / 2
            photobomb_spot_effect["steps"].append({
                "time": off_time,
                "channels": {"total_dimming": 64, "r_dimming": 64, "g_dimming": 64, "b_dimming": 64, "w_dimming": 64, "total_strobe": 0, "function_selection": 0, "function_speed": 0}
            })
    
    # Ensure the effect ends with lights off
    photobomb_spot_effect["steps"].append({
        "time": 15.0,
        "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}
    })
    
    logger.debug(f"Created PhotoBomb-Spot effect: {photobomb_spot_effect}")
    logger.info(f"PhotoBomb-Spot effect created with {len(photobomb_spot_effect['steps'])} steps over {photobomb_spot_effect['duration']} seconds")
    return photobomb_spot_effect
