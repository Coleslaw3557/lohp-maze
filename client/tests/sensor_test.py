import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal
from collections import deque

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Define laser transmitter and receiver pins
laser_transmitters = {
    'Cop Dodge': 17,
    'Gate': 22,
    'Guy Line': 24,
    'Sparkle Pony': 5,
    'Porto': 13
}

laser_receivers = {
    'Cop Dodge': 27,
    'Gate': 23,
    'Guy Line': 25,
    'Sparkle Pony': 6,
    'Porto': 19
}

# Set up laser transmitter pins as outputs and receiver pins as inputs
for pin in laser_transmitters.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # Turn on all lasers

for pin in laser_receivers.values():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Set up I2C for ADS1115
i2c = board.I2C()
try:
    ads1 = ADS.ADS1115(i2c, address=0x48)  # ADC1 for Gate Room
    ads2 = ADS.ADS1115(i2c, address=0x49)  # ADC2 for Porto Room

    # Set up analog inputs
    gate_resistor_ladder1 = AnalogIn(ads1, ADS.P0)
    gate_resistor_ladder2 = AnalogIn(ads1, ADS.P1)
    gate_buttons = AnalogIn(ads1, ADS.P2)
    porto_piezo1 = AnalogIn(ads2, ADS.P0)
    porto_piezo2 = AnalogIn(ads2, ADS.P1)
    porto_piezo3 = AnalogIn(ads2, ADS.P2)
    adc_available = True

    # Set up low-pass filters for each analog input
    filter_size = 10
    filters = {
        'gate_resistor_ladder1': deque(maxlen=filter_size),
        'gate_resistor_ladder2': deque(maxlen=filter_size),
        'gate_buttons': deque(maxlen=filter_size),
        'porto_piezo1': deque(maxlen=filter_size),
        'porto_piezo2': deque(maxlen=filter_size),
        'porto_piezo3': deque(maxlen=filter_size),
    }

    # Define thresholds for connected vs unconnected states
    CONNECTED_THRESHOLD = 100  # Adjust this value based on your specific setup
except OSError:
    print("Failed to initialize ADCs. Analog sensors will not be available.")
    adc_available = False

# Set up Terminal for TUI
term = Terminal()

def get_filtered_value(sensor_name, raw_value):
    filters[sensor_name].append(raw_value)
    return sum(filters[sensor_name]) / len(filters[sensor_name])

def is_connected(value):
    return value > CONNECTED_THRESHOLD

def get_button_state(value):
    if not is_connected(value):
        return "Disconnected"
    elif value < 5000:
        return "Button 1"
    elif value < 10000:
        return "Button 2"
    elif value < 15000:
        return "Button 3"
    elif value < 20000:
        return "Button 4"
    else:
        return "No button"

def get_sensor_data():
    data = []
    for room, pin in laser_receivers.items():
        try:
            status = "Intact" if GPIO.input(pin) == GPIO.LOW else "Broken"
        except:
            status = "Error"
        data.append((f"GPIO {pin}", f"{room} Laser", room, status))
    
    adc_data = [
        ("ADC1 A0", "Resistor Ladder 1", "Gate"),
        ("ADC1 A1", "Resistor Ladder 2", "Gate"),
        ("ADC1 A2", "Buttons", "Gate"),
        ("ADC2 A0", "Piezo 1", "Porto"),
        ("ADC2 A1", "Piezo 2", "Porto"),
        ("ADC2 A2", "Piezo 3", "Porto")
    ]
    
    for adc, sensor, room in adc_data:
        if adc_available:
            try:
                if adc == "ADC1 A0":
                    filtered_value = get_filtered_value('gate_resistor_ladder1', gate_resistor_ladder1.value)
                    value = f"{filtered_value:.0f} ({gate_resistor_ladder1.voltage:.2f}V)" if is_connected(filtered_value) else "Disconnected"
                elif adc == "ADC1 A1":
                    filtered_value = get_filtered_value('gate_resistor_ladder2', gate_resistor_ladder2.value)
                    value = f"{filtered_value:.0f} ({gate_resistor_ladder2.voltage:.2f}V)" if is_connected(filtered_value) else "Disconnected"
                elif adc == "ADC1 A2":
                    filtered_value = get_filtered_value('gate_buttons', gate_buttons.value)
                    value = get_button_state(filtered_value)
                elif adc == "ADC2 A0":
                    filtered_value = get_filtered_value('porto_piezo1', porto_piezo1.value)
                    value = f"{filtered_value:.0f} ({porto_piezo1.voltage:.2f}V)" if is_connected(filtered_value) else "Disconnected"
                elif adc == "ADC2 A1":
                    filtered_value = get_filtered_value('porto_piezo2', porto_piezo2.value)
                    value = f"{filtered_value:.0f} ({porto_piezo2.voltage:.2f}V)" if is_connected(filtered_value) else "Disconnected"
                elif adc == "ADC2 A2":
                    filtered_value = get_filtered_value('porto_piezo3', porto_piezo3.value)
                    value = f"{filtered_value:.0f} ({porto_piezo3.voltage:.2f}V)" if is_connected(filtered_value) else "Disconnected"
            except:
                value = "Error"
        else:
            value = "Offline"
        data.append((adc, sensor, room, value))
    
    return data

def display_tui():
    print(term.clear())
    print(term.move_y(0) + term.center("LoHP Maze Sensor Data"))
    print(term.move_y(2) + term.center("Press 'q' to quit"))
    
    data = get_sensor_data()
    for i, (pin, sensor, room, value) in enumerate(data):
        y = i + 4
        print(term.move_xy(0, y) + f"{pin:<10} {sensor:<20} {room:<15} {value}")

try:
    with term.cbreak(), term.hidden_cursor():
        while True:
            display_tui()
            
            if term.inkey(timeout=0.5) == 'q':
                break

except KeyboardInterrupt:
    pass
finally:
    # Turn off all lasers
    for pin in laser_transmitters.values():
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print(term.clear())
