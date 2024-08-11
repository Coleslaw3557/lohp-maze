import math
import logging

logger = logging.getLogger(__name__)

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

def generate_theme_values(theme_data, current_time, master_brightness, room_index=0, total_rooms=1):
    channels = {}
    overall_brightness = theme_data.get('overall_brightness', 0.5) * master_brightness
    color_variation = theme_data.get('color_variation', 0.5)
    intensity_fluctuation = theme_data.get('intensity_fluctuation', 0.5)
    transition_speed = theme_data.get('transition_speed', 0.5)

    # Variable speed factor with increased variation
    speed_variation = math.sin(current_time * 0.1) * 0.5 + 1.5  # Varies between 1 and 2
    time_factor = current_time * transition_speed * speed_variation

    sin_time = math.sin(time_factor)
    sin_time_slow = math.sin(time_factor * 0.2)
    sin_time_medium = math.sin(time_factor * 0.5)
    sin_time_fast = math.sin(time_factor * 1.5)

    color_wheel_speed = theme_data.get('color_wheel_speed', 0.2) * speed_variation
    room_transition_speed = theme_data.get('room_transition_speed', 0.05) * speed_variation
    room_offset = (room_index / total_rooms + time_factor * room_transition_speed) % 1

    base_hue = theme_data.get('base_hue', 0)
    hue_range = theme_data.get('hue_range', 0.5)
    hue = (base_hue + (math.sin(time_factor * color_wheel_speed + room_offset) * 0.5 + 0.5) * hue_range) % 1
    saturation = 0.6 + sin_time_medium * 0.4 * color_variation
    value = overall_brightness * (0.4 + sin_time * intensity_fluctuation * 0.6)

    if 'blue_green_balance' in theme_data:  # Ocean theme
        wave_effect = math.sin(time_factor * 0.7) * theme_data.get('wave_effect', 0.4)
        depth_illusion = math.sin(time_factor * 0.5) * theme_data.get('depth_illusion', 0.5)
        bioluminescence = (math.sin(time_factor * 1.2) * 0.5 + 0.5) * theme_data.get('bioluminescence', 0.4)
        hue = (hue + 0.1 * math.sin(time_factor * 0.3)) % 1  # Slight hue shift
        value += wave_effect + depth_illusion
        saturation = max(0, min(1, saturation - bioluminescence * 0.3))  # Bioluminescence affects saturation
    elif 'green_yellow_balance' in theme_data:  # Jungle theme
        leaf_rustle = math.sin(time_factor * 1.1) * theme_data.get('leaf_rustle_effect', 0.4)
        sunbeam = (math.sin(time_factor * 0.6) * 0.5 + 0.5) * theme_data.get('sunbeam_effect', 0.5)
        flower_bloom = (math.sin(time_factor * 0.8) * 0.5 + 0.5) * theme_data.get('flower_bloom', 0.4)
        hue = (hue + 0.05 * math.sin(time_factor * 0.4)) % 1  # Slight hue shift
        value += leaf_rustle
        saturation = max(0, min(1, saturation + sunbeam * 0.2 - flower_bloom * 0.1))
    elif 'geometric_patterns' in theme_data:  # MazeMadness theme
        geometric = math.sin(time_factor * 1.2) * theme_data.get('geometric_patterns', 0.6)
        perspective = math.sin(time_factor * 0.9) * theme_data.get('perspective_shift', 0.5)
        neon_glow = (math.sin(time_factor * 1.5) * 0.5 + 0.5) * theme_data.get('neon_glow', 0.5)
        hue = (hue + 0.2 * math.sin(time_factor * 0.7)) % 1  # More pronounced hue shift
        value += geometric + perspective
        saturation = max(0, min(1, saturation + neon_glow * 0.3))
    elif 'joy_factor' in theme_data:  # TimsFav theme
        joy_factor = theme_data.get('joy_factor', 0.7)
        excitement_factor = theme_data.get('excitement_factor', 0.8)
        ecstasy_factor = theme_data.get('ecstasy_factor', 0.6)
        kaleidoscope = math.sin(time_factor * 1.3) * theme_data.get('kaleidoscope_effect', 0.5)
        fractal = math.sin(time_factor * 1.7) * theme_data.get('fractal_patterns', 0.4)
        hue = (hue + 0.15 * math.sin(time_factor * joy_factor) + 
               0.15 * math.cos(time_factor * excitement_factor) + 
               0.15 * math.sin(2 * time_factor * ecstasy_factor)) % 1
        value += kaleidoscope + fractal
        saturation = max(0, min(1, saturation + 0.2 * math.sin(time_factor * 1.1)))
    elif 'sand_ripple_effect' in theme_data:  # DesertDream theme
        sand_ripple = math.sin(time_factor * 0.8) * theme_data.get('sand_ripple_effect', 0.4)
        mirage = (math.sin(time_factor * 0.5) * 0.5 + 0.5) * theme_data.get('mirage_illusion', 0.5)
        heat_wave = math.sin(time_factor * 1.2) * theme_data.get('heat_wave_distortion', 0.3)
        hue = (hue + 0.05 * math.sin(time_factor * 0.3)) % 1  # Slight hue shift
        value += sand_ripple + heat_wave
        saturation = max(0, min(1, saturation - mirage * 0.2))

    # Ensure value and saturation don't exceed 1.0 or go below 0.0
    value = max(0, min(value, 1.0))
    saturation = max(0, min(saturation, 1.0))

    r, g, b = hsv_to_rgb(hue, saturation, value)

    channels['total_dimming'] = int(value * 255)
    channels['r_dimming'] = int(r * 255)
    channels['g_dimming'] = int(g * 255)
    channels['b_dimming'] = int(b * 255)
    channels['w_dimming'] = int(value * 64)  # Add a subtle white component

    return channels

def get_effect_step_values(effect_data):
    def get_values(elapsed_time):
        for i, step in enumerate(effect_data['steps']):
            if elapsed_time <= step['time']:
                if i == 0:
                    return [step['channels'].get(channel, 0) for channel in ['total_dimming', 'r_dimming', 'g_dimming', 'b_dimming', 'w_dimming', 'total_strobe', 'function_selection', 'function_speed']]
                else:
                    prev_step = effect_data['steps'][i-1]
                    t = (elapsed_time - prev_step['time']) / (step['time'] - prev_step['time'])
                    return [
                        int(prev_step['channels'].get(channel, 0) + t * (step['channels'].get(channel, 0) - prev_step['channels'].get(channel, 0)))
                        for channel in ['total_dimming', 'r_dimming', 'g_dimming', 'b_dimming', 'w_dimming', 'total_strobe', 'function_selection', 'function_speed']
                    ]
        return [0] * 8  # Return all zeros if elapsed_time is beyond the last step
    return get_values
