import logging

logger = logging.getLogger(__name__)

def create_lightning_effect():
    lightning_effect = {
        "duration": 3.5,
        "description": "Simulates a lightning strike with bright flashes, matching the audio spectrogram",
        "steps": [
            {"time": 0.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.5, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.6, "channels": {"total_dimming": 128, "r_dimming": 128, "g_dimming": 128, "b_dimming": 128, "w_dimming": 128, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.7, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 0.8, "channels": {"total_dimming": 64, "r_dimming": 64, "g_dimming": 64, "b_dimming": 64, "w_dimming": 64, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.0, "channels": {"total_dimming": 192, "r_dimming": 192, "g_dimming": 192, "b_dimming": 192, "w_dimming": 192, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.2, "channels": {"total_dimming": 128, "r_dimming": 128, "g_dimming": 128, "b_dimming": 128, "w_dimming": 128, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.5, "channels": {"total_dimming": 192, "r_dimming": 192, "g_dimming": 192, "b_dimming": 192, "w_dimming": 192, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 1.8, "channels": {"total_dimming": 96, "r_dimming": 96, "g_dimming": 96, "b_dimming": 96, "w_dimming": 96, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 2.2, "channels": {"total_dimming": 128, "r_dimming": 128, "g_dimming": 128, "b_dimming": 128, "w_dimming": 128, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 2.6, "channels": {"total_dimming": 64, "r_dimming": 64, "g_dimming": 64, "b_dimming": 64, "w_dimming": 64, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 3.0, "channels": {"total_dimming": 32, "r_dimming": 32, "g_dimming": 32, "b_dimming": 32, "w_dimming": 32, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": 3.5, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ]
    }
    logger.debug(f"Created Lightning effect: {lightning_effect}")
    logger.info(f"Lightning effect created with {len(lightning_effect['steps'])} steps over {lightning_effect['duration']} seconds")
    return lightning_effect
