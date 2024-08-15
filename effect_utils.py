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

def generate_theme_values(theme_data, current_time, master_brightness, room_index=0, total_rooms=1, temporary_values=None):
    channels = {}
    overall_brightness = theme_data.get('overall_brightness', 0.8) * master_brightness
    temporary_values = temporary_values or {}
    color_variation = temporary_values.get('color-variation', theme_data.get('color_variation', 0.8))
    intensity_fluctuation = temporary_values.get('intensity-fluctuation', theme_data.get('intensity_fluctuation', 0.6))
    transition_speed = temporary_values.get('transition-speed', theme_data.get('transition_speed', 0.7))

    # Use multiple time factors for more complex patterns
    time_factor_slow = current_time * transition_speed * 0.05
    time_factor_medium = current_time * transition_speed * 0.2
    time_factor_fast = current_time * transition_speed * 0.8
    time_factor_very_fast = current_time * transition_speed * 3

    # Create more complex waveforms
    wave_slow = math.sin(time_factor_slow)
    wave_medium = math.sin(time_factor_medium)
    wave_fast = math.sin(time_factor_fast)
    wave_very_fast = math.sin(time_factor_very_fast)
    wave_complex = (wave_slow + wave_medium + wave_fast + wave_very_fast) / 4

    # Add room-specific offsets for wave-like effects across rooms
    room_offset = (room_index / total_rooms) * 2 * math.pi
    room_wave = math.sin(time_factor_medium + room_offset)

    color_wheel_speed = temporary_values.get('color-wheel-speed', theme_data.get('color_wheel_speed', 0.3))
    room_transition_speed = theme_data.get('room_transition_speed', 0.08)
    wave_effect = temporary_values.get('wave-effect', theme_data.get('wave_effect', 0.7))

    base_hue = theme_data.get('base_hue', 0)
    hue_range = theme_data.get('hue_range', 0.7)
    hue = (base_hue + (wave_complex * 0.5 + 0.5) * hue_range + time_factor_slow * color_wheel_speed + room_wave * 0.1) % 1
    
    saturation_min = theme_data.get('saturation_min', 0.7)
    saturation_max = theme_data.get('saturation_max', 1.0)
    saturation = saturation_min + (saturation_max - saturation_min) * ((wave_medium + room_wave) * 0.25 + 0.5)
    
    value_min = theme_data.get('value_min', 0.6)
    value_max = theme_data.get('value_max', 1.0)
    value = value_min + (value_max - value_min) * ((wave_fast + room_wave) * 0.25 + 0.5) * overall_brightness

    # Apply theme-specific effects
    if 'neon_pulse' in theme_data:  # NeonNightlife theme
        neon_pulse = (math.sin(time_factor_fast * 3 + room_offset) * 0.5 + 0.5) * theme_data.get('neon_pulse', 0.9)
        strobe = (math.sin(time_factor_very_fast * 10 + room_offset) * 0.5 + 0.5) * theme_data.get('strobe_frequency', 0.3)
        hue = (hue + neon_pulse * 0.2) % 1
        value = max(value_min, min(value_max, value + neon_pulse * 0.3 + strobe * 0.2))
    elif 'wave_effect' in theme_data:  # TropicalParadise theme
        wave = math.sin(time_factor_medium * 1.5 + room_offset) * theme_data.get('wave_effect', 0.7)
        sunset = (math.sin(time_factor_slow * 0.5 + room_offset) * 0.5 + 0.5) * theme_data.get('sunset_glow', 0.8)
        hue = (hue + sunset * 0.1 + wave * 0.05) % 1
        saturation = max(saturation_min, min(saturation_max, saturation + wave * 0.2))
        value = max(value_min, min(value_max, value + sunset * 0.3 + wave * 0.1))
    elif 'neon_flicker' in theme_data:  # CyberPunk theme
        flicker = random.uniform(0.8, 1.0) * theme_data.get('neon_flicker', 0.8)
        data_stream = (math.sin(time_factor_very_fast * 5 + room_offset) * 0.5 + 0.5) * theme_data.get('data_stream', 0.7)
        hue = (hue + data_stream * 0.3) % 1
        value = max(value_min, min(value_max, value * flicker + data_stream * 0.2))
    elif 'fairy_lights' in theme_data:  # EnchantedForest theme
        fairy_lights = (math.sin(time_factor_fast * 4 + room_offset) * 0.5 + 0.5) * theme_data.get('fairy_lights', 0.6)
        moonbeam = (math.sin(time_factor_slow * 0.3 + room_offset) * 0.5 + 0.5) * theme_data.get('moonbeam', 0.5)
        hue = (hue + moonbeam * 0.1 + fairy_lights * 0.05) % 1
        saturation = max(saturation_min, min(saturation_max, saturation - moonbeam * 0.3 + fairy_lights * 0.2))
        value = max(value_min, min(value_max, value + fairy_lights * 0.4 + moonbeam * 0.2))
    elif 'starfield_twinkle' in theme_data:  # CosmicVoyage theme
        twinkle = random.uniform(0.7, 1.0) * theme_data.get('starfield_twinkle', 0.8)
        nebula = (math.sin(time_factor_medium * 0.7 + room_offset) * 0.5 + 0.5) * theme_data.get('nebula_swirl', 0.7)
        hue = (hue + nebula * 0.2 + twinkle * 0.05) % 1
        saturation = max(saturation_min, min(saturation_max, saturation + nebula * 0.3 + twinkle * 0.1))
        value = max(value_min, min(value_max, value * twinkle + nebula * 0.2))

    # Add some randomness to prevent static patterns
    hue = (hue + random.uniform(-0.03, 0.03)) % 1
    saturation = max(saturation_min, min(saturation_max, saturation + random.uniform(-0.05, 0.05)))
    value = max(value_min, min(value_max, value + random.uniform(-0.05, 0.05)))

    # Generate complementary and analogous colors for more vibrant mixtures
    complementary_hue = (hue + 0.5) % 1
    analogous_hue1 = (hue + 0.0833) % 1  # 30 degrees
    analogous_hue2 = (hue - 0.0833) % 1  # -30 degrees

    r, g, b = hsv_to_rgb(hue, saturation, value)
    r_comp, g_comp, b_comp = hsv_to_rgb(complementary_hue, saturation, value)
    r_ana1, g_ana1, b_ana1 = hsv_to_rgb(analogous_hue1, saturation, value)
    r_ana2, g_ana2, b_ana2 = hsv_to_rgb(analogous_hue2, saturation, value)

    # Determine dominant color channels
    color_values = [r, g, b]
    max_color = max(color_values)
    secondary_color = sorted(color_values, reverse=True)[1]
    
    # Calculate color ratios
    primary_ratio = 1.0
    secondary_ratio = secondary_color / max_color if max_color > 0 else 0
    tertiary_ratio = 0.0

    # Assign color values ensuring only one or two channels are dominant
    r_final = r * primary_ratio if r == max_color else (r * secondary_ratio if r == secondary_color else r * tertiary_ratio)
    g_final = g * primary_ratio if g == max_color else (g * secondary_ratio if g == secondary_color else g * tertiary_ratio)
    b_final = b * primary_ratio if b == max_color else (b * secondary_ratio if b == secondary_color else b * tertiary_ratio)

    channels['total_dimming'] = int(value * 255)
    channels['r_dimming'] = int(r_final * 255)
    channels['g_dimming'] = int(g_final * 255)
    channels['b_dimming'] = int(b_final * 255)
    channels['w_dimming'] = 0  # Remove white component to avoid creating white light

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
