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

    time_factor = current_time * transition_speed * 0.1  # Slow down the transition
    sin_time = math.sin(time_factor)
    sin_time_slow = math.sin(time_factor * 0.1)
    sin_time_medium = math.sin(time_factor * 0.2)

    if 'blue_green_balance' in theme_data:  # Ocean theme
        hue = 0.5 + sin_time_slow * 0.05  # Reduce hue variation
        blue_green_balance = theme_data.get('blue_green_balance', 0.8)
        saturation = 0.8 + sin_time_medium * 0.1 * color_variation  # Reduce saturation variation
    elif 'green_blue_balance' in theme_data:  # Jungle theme
        hue = 0.3 + sin_time_slow * 0.05  # Reduce hue variation
        green_blue_balance = theme_data.get('green_blue_balance', 0.9)
        saturation = 0.9 + sin_time_medium * 0.05 * color_variation  # Reduce saturation variation
    elif 'color_wheel_speed' in theme_data:  # MazeMadness theme
        color_wheel_speed = theme_data.get('color_wheel_speed', 0.1)
        room_transition_speed = theme_data.get('room_transition_speed', 0.02)
        room_offset = (room_index / total_rooms + time_factor * room_transition_speed) % 1
        hue = (time_factor * color_wheel_speed + room_offset) % 1  # Color wheel effect
        saturation = 0.9 + sin_time_medium * 0.1 * color_variation
    else:
        hue = 0.5 + sin_time_slow * 0.1  # Reduce hue variation
        saturation = 0.8 + sin_time_medium * 0.1 * color_variation  # Reduce saturation variation

    value = overall_brightness * (1 + sin_time * intensity_fluctuation * 0.5)  # Reduce intensity fluctuation
    r, g, b = hsv_to_rgb(hue, saturation, value)

    if 'blue_green_balance' in theme_data:  # Ocean theme
        b *= blue_green_balance
        g *= (1 - blue_green_balance)
    elif 'green_blue_balance' in theme_data:  # Jungle theme
        g *= green_blue_balance
        b *= (1 - green_blue_balance)

    channels['total_dimming'] = int(value * 255)
    channels['r_dimming'] = int(r * 255)
    channels['g_dimming'] = int(g * 255)
    channels['b_dimming'] = int(b * 255)
    channels['w_dimming'] = int(min(r, g, b) * 12.75)  # 255 * 0.05 = 12.75

    strobe_speed = theme_data.get('strobe_speed', 0)
    channels['total_strobe'] = int(127 + sin_time * strobe_speed * 32) if strobe_speed > 0 else 0  # Reduce strobe intensity

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
