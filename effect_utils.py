import math
import logging
import random

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
    overall_brightness = theme_data.get('overall_brightness', 0.8) * master_brightness
    color_variation = theme_data.get('color_variation', 0.8)
    intensity_fluctuation = theme_data.get('intensity_fluctuation', 0.6)
    transition_speed = theme_data.get('transition_speed', 0.7)

    # Use multiple time factors for more complex patterns
    time_factor_slow = current_time * transition_speed * 0.1
    time_factor_medium = current_time * transition_speed * 0.5
    time_factor_fast = current_time * transition_speed
    time_factor_very_fast = current_time * transition_speed * 2

    # Create more complex waveforms
    wave_slow = math.sin(time_factor_slow)
    wave_medium = math.sin(time_factor_medium)
    wave_fast = math.sin(time_factor_fast)
    wave_very_fast = math.sin(time_factor_very_fast)
    wave_complex = (wave_slow + wave_medium + wave_fast + wave_very_fast) / 4

    color_wheel_speed = theme_data.get('color_wheel_speed', 0.3)
    room_transition_speed = theme_data.get('room_transition_speed', 0.08)
    room_offset = (room_index / total_rooms + time_factor_medium * room_transition_speed) % 1

    base_hue = theme_data.get('base_hue', 0)
    hue_range = theme_data.get('hue_range', 0.7)
    hue = (base_hue + (wave_complex * 0.5 + 0.5) * hue_range + time_factor_slow * color_wheel_speed) % 1
    saturation = 0.7 + wave_medium * 0.3 * color_variation
    value = overall_brightness * (0.7 + wave_fast * intensity_fluctuation * 0.3)

    if 'blue_green_balance' in theme_data:  # Ocean theme
        wave_effect = math.sin(time_factor_fast * 1.5) * theme_data.get('wave_effect', 0.6)
        depth_illusion = math.sin(time_factor_medium * 0.7) * theme_data.get('depth_illusion', 0.7)
        bioluminescence = (math.sin(time_factor_very_fast * 2) * 0.5 + 0.5) * theme_data.get('bioluminescence', 0.6)
        hue = (0.5 + 0.1 * wave_slow + 0.05 * wave_fast + 0.02 * wave_very_fast) % 1  # Cyan to blue range
        value = max(0.2, min(1.0, value + wave_effect * 0.3 + depth_illusion * 0.2 + bioluminescence * 0.1))
        saturation = max(0.5, min(1.0, saturation + bioluminescence * 0.3))
    elif 'green_yellow_balance' in theme_data:  # Jungle theme
        leaf_rustle = math.sin(time_factor_fast * 2) * theme_data.get('leaf_rustle_effect', 0.6)
        sunbeam = (math.sin(time_factor_medium * 0.5) * 0.5 + 0.5) * theme_data.get('sunbeam_effect', 0.7)
        flower_bloom = (math.sin(time_factor_slow * 0.3) * 0.5 + 0.5) * theme_data.get('flower_bloom', 0.6)
        hue = (0.2 + 0.1 * wave_medium + 0.05 * wave_fast) % 1  # Green to yellow-green range
        value = max(0.3, min(1.0, value + leaf_rustle * 0.2 + sunbeam * 0.3 + flower_bloom * 0.1))
        saturation = max(0.6, min(1.0, saturation + flower_bloom * 0.2 + leaf_rustle * 0.1))
    elif 'geometric_patterns' in theme_data:  # MazeMadness theme
        geometric = math.sin(time_factor_fast * 3) * theme_data.get('geometric_patterns', 0.8)
        perspective = math.sin(time_factor_medium * 1.5) * theme_data.get('perspective_shift', 0.7)
        neon_glow = (math.sin(time_factor_very_fast * 2.5) * 0.5 + 0.5) * theme_data.get('neon_glow', 0.7)
        hue = (wave_complex * 0.5 + 0.5 + time_factor_fast * color_wheel_speed) % 1  # Full color range
        value = max(0.4, min(1.0, value + geometric * 0.3 + perspective * 0.2 + neon_glow * 0.2))
        saturation = max(0.7, min(1.0, saturation + neon_glow * 0.3 + geometric * 0.1))
    elif 'joy_factor' in theme_data:  # TimsFav theme
        joy_wave = math.sin(time_factor_fast * 2.5) * theme_data.get('joy_factor', 0.8)
        excitement_wave = math.sin(time_factor_medium * 1.8) * theme_data.get('excitement_factor', 0.9)
        ecstasy_wave = math.sin(time_factor_slow * 1.2) * theme_data.get('ecstasy_factor', 0.7)
        kaleidoscope = math.sin(time_factor_very_fast * 3) * theme_data.get('kaleidoscope_effect', 0.6)
        hue = (joy_wave * 0.3 + excitement_wave * 0.3 + ecstasy_wave * 0.4 + time_factor_fast * color_wheel_speed) % 1
        value = max(0.5, min(1.0, value + (joy_wave + excitement_wave + ecstasy_wave + kaleidoscope) * 0.15))
        saturation = max(0.7, min(1.0, 0.8 + (joy_wave + excitement_wave + ecstasy_wave + kaleidoscope) * 0.05))
    elif 'sand_ripple_effect' in theme_data:  # DesertDream theme
        sand_ripple = math.sin(time_factor_medium * 1.5) * theme_data.get('sand_ripple_effect', 0.6)
        mirage = (math.sin(time_factor_slow * 0.7) * 0.5 + 0.5) * theme_data.get('mirage_illusion', 0.7)
        heat_wave = math.sin(time_factor_fast * 2) * theme_data.get('heat_wave_distortion', 0.5)
        oasis = (math.sin(time_factor_very_fast * 1.5) * 0.5 + 0.5) * theme_data.get('oasis_glow', 0.4)
        hue = (0.08 + 0.04 * wave_slow + 0.02 * wave_medium) % 1  # Warm desert colors
        value = max(0.3, min(0.9, value + sand_ripple * 0.2 + heat_wave * 0.1 + oasis * 0.1))
        saturation = max(0.4, min(0.9, saturation - mirage * 0.3 + oasis * 0.2))

    # Add some randomness to prevent static patterns
    hue = (hue + random.uniform(-0.02, 0.02)) % 1
    saturation = max(0.1, min(1.0, saturation + random.uniform(-0.05, 0.05)))
    value = max(0.1, min(1.0, value + random.uniform(-0.05, 0.05)))

    r, g, b = hsv_to_rgb(hue, saturation, value)

    channels['total_dimming'] = int(value * 255)
    channels['r_dimming'] = int(r * 255)
    channels['g_dimming'] = int(g * 255)
    channels['b_dimming'] = int(b * 255)
    channels['w_dimming'] = 0  # Remove white component

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
