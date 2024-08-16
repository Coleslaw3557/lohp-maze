import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal
from collections import deque
import logging

def test_level_shifter(input_pin, output_pin):
    GPIO.setup(input_pin, GPIO.OUT)
    
    for state in [GPIO.HIGH, GPIO.LOW]:
        GPIO.output(input_pin, state)
        time.sleep(0.1)
        logging.debug(f"Set Input Pin {input_pin} to {state}")
    
    GPIO.setup(input_pin, GPIO.IN)
    
    logging.info(f"Level Shifter Test: Input Pin {input_pin} tested, Output Pin {output_pin} not connected")
    return f"Input {input_pin} tested, Output {output_pin} not connected"

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    for pin in laser_transmitters.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # Turn on all lasers

    for pin in laser_receivers.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

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

# Set up GPIO
setup_gpio()

# Set up logging
logging.basicConfig(filename='sensor_test.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
# Add a stream handler to print DEBUG messages to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logging.getLogger('').addHandler(console_handler)

# Set up I2C for ADS1115
i2c = busio.I2C(board.SCL, board.SDA)
# Set up ADCs and analog inputs
adc_available = False
ads1 = None
ads2 = None
gate_resistor_ladder1 = gate_resistor_ladder2 = gate_buttons = None
porto_piezo1 = porto_piezo2 = porto_piezo3 = None
filters = {}
CONNECTED_THRESHOLD = 100

def initialize_adc():
    global adc_available, ads1, ads2, gate_resistor_ladder1, gate_resistor_ladder2, gate_buttons, porto_piezo1, porto_piezo2, porto_piezo3, filters, CONNECTED_THRESHOLD
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
        global CONNECTED_THRESHOLD
        CONNECTED_THRESHOLD = 100  # Adjust this value based on your specific setup
        logging.info("ADCs initialized successfully")
    except OSError as e:
        logging.error(f"Failed to initialize ADCs. Error: {e}")
        adc_available = False

initialize_adc()

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
    elif value < 8192:  # 1/4 of max value (32768)
        return "Button 1"
    elif value < 16384:  # 1/2 of max value
        return "Button 2"
    elif value < 24576:  # 3/4 of max value
        return "Button 3"
    elif value < 32768:  # Max value
        return "Button 4"
    else:
        return "No button"

def get_sensor_data():
    data = []
    
    # Test level shifters
    ls1_status = test_level_shifter(17, 27)
    ls2_status = test_level_shifter(24, 25)
    data.append(("LS1", "Level Shifter 1", "All", ls1_status))
    data.append(("LS2", "Level Shifter 2", "All", ls2_status))
    
    # Test ADCs
    adc_data = [
        ("ADC1 A0", "Channel 0", "Gate", gate_resistor_ladder1),
        ("ADC1 A1", "Channel 1", "Gate", gate_resistor_ladder2),
        ("ADC1 A2", "Channel 2", "Gate", gate_buttons),
        ("ADC2 A0", "Channel 0", "Porto", porto_piezo1),
        ("ADC2 A1", "Channel 1", "Porto", porto_piezo2),
        ("ADC2 A2", "Channel 2", "Porto", porto_piezo3)
    ]
    
    for adc, channel, room, analog_in in adc_data:
        if adc_available:
            status = read_adc_with_retry(adc, channel, analog_in)
        else:
            status = "Offline"
        data.append((adc, channel, room, status))
    
    return data

def read_adc_with_retry(adc, channel, analog_in, max_attempts=5, delay=0.2):
    for attempt in range(max_attempts):
        try:
            value = analog_in.value
            voltage = analog_in.voltage
            return f"Value: {value}, Voltage: {voltage:.2f}V"
        except Exception as e:
            logging.error(f"Error reading {adc} {channel}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(delay)
    
    logging.error(f"Failed to read {adc} {channel} after {max_attempts} attempts")
    return "Failed after multiple attempts"

def display_tui():
    print(term.clear())
    print(term.move_y(0) + term.center("LoHP Maze Hardware Test"))
    print(term.move_y(2) + term.center("Press 'q' to quit"))
    
    data = get_sensor_data()
    for i, (component, description, location, status) in enumerate(data):
        y = i + 4
        print(term.move_xy(0, y) + f"{component:<10} {description:<20} {location:<15} {status}")

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
