import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal
from collections import deque

# Constants for knock detection
KNOCK_THRESHOLD = 0.05  # Lowered threshold for more sensitivity with piezo
VOLTAGE_CHANGE_THRESHOLD = 0.01  # Lowered minimum voltage change to consider as a knock
COOLDOWN_TIME = 0.2  # Reduced cooldown time for quicker response
DEBUG_THRESHOLD = 0.005  # Lowered threshold for more detailed debug output
CONNECTED_THRESHOLD = 0.3  # Adjusted threshold for detecting connected sensors
RESISTOR_LADDER_ADC = "ADC1 A0"  # Specify which ADC is used for the resistor ladder

# Define unit configurations
UNIT_CONFIGS = {
    'A': {
        'name': 'UNIT-A',
        'lasers': {
            'Entrance': {'LT': 4, 'LR': 17},
            'Cuddle Cross': {'LT': 18, 'LR': 27},
            'Photo Bomb': {'LT': 22, 'LR': 23},
            'No Friends Monday': {'LT': 24, 'LR': 25},
            'Exit': {'LT': 5, 'LR': 6}
        },
        'adc': {
            'Cuddle Cross': {'adc': 'ads1', 'channel': ADS.P0}
        }
    },
    'B': {
        'name': 'UNIT-B',
        'lasers': {
            'Cop Dodge': {'LT': 17, 'LR': 27},
            'Gate': {'LT': 22, 'LR': 5},
            'Guy Line': {'LT': 24, 'LR': 6},
            'Sparkle Pony': {'LT': 25, 'LR': 13},
            'Porto': {'LT': 19, 'LR': 26}
        },
        'adc': {
            'Gate': {'adc': 'ads1', 'channel': ADS.P0},
            'Porto': {'adc': 'ads2', 'channel': ADS.P0}
        }
    },
    'C': {
        'name': 'UNIT-C',
        'lasers': {
            'Temple': {'LT': 4, 'LR': 17},
            'Deep Playa Handshake': {'LT': 18, 'LR': 27},
            'Bike Lock': {'LT': 22, 'LR': 23},
            'Vertical Moop March': {'LT': 24, 'LR': 25},
            'Monkey': {'LT': 5, 'LR': 6}
        },
        'adc': {
            'Deep Playa Handshake': {'adc': 'ads1', 'channel': ADS.P0}
        }
    }
}

# Initialize current unit
current_unit = 'B'  # Default to Unit B

def test_level_shifter(input_pin, output_pin):
    GPIO.setup(input_pin, GPIO.OUT)
    GPIO.setup(output_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    results = []
    for state in [GPIO.HIGH, GPIO.LOW]:
        GPIO.output(input_pin, state)
        time.sleep(0.1)
        output_state = GPIO.input(output_pin)
        results.append((state, output_state))
    
    GPIO.setup(input_pin, GPIO.IN)
    
    return results

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    config = UNIT_CONFIGS[current_unit]
    for room, pins in config['lasers'].items():
        GPIO.setup(pins['LT'], GPIO.OUT)
        GPIO.output(pins['LT'], GPIO.HIGH)  # Turn on all lasers
        GPIO.setup(pins['LR'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Use pull-down resistor

# Set up GPIO
setup_gpio()

# Set up I2C for ADS1115
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)  # Lower the I2C frequency to 100 kHz
# Set up ADCs and analog inputs
adc_available = False
ads1 = None
ads2 = None
analog_inputs = {}
filters = {}
CONNECTED_THRESHOLD = 0.3
RESISTOR_LADDER_THRESHOLD = 0.1  # Adjust this value based on your resistor ladder setup

def check_i2c_devices():
    print("Checking I2C devices...")
    try:
        import subprocess
        result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error checking I2C devices: {str(e)}")

def initialize_adc():
    global adc_available, ads1, ads2, analog_inputs
    adc_available = False
    ads1 = ads2 = None

    def init_adc(address):
        try:
            adc = ADS.ADS1115(i2c, address=address, gain=1)
            adc.data_rate = 8
            print(f"ADC initialized at address 0x{address:02X}")
            return adc
        except Exception as e:
            print(f"Failed to initialize ADC at address 0x{address:02X}: {str(e)}")
            return None

    ads1 = init_adc(0x48)
    ads2 = init_adc(0x49)

    if ads1 is None and ads2 is None:
        print("Failed to initialize both ADCs")
        return

    def setup_analog_in(adc, channel):
        if adc is not None:
            try:
                analog_in = AnalogIn(adc, channel)
                # Test read to ensure the channel is working
                _ = analog_in.value
                return analog_in
            except Exception as e:
                adc_id = "0x48" if adc == ads1 else "0x49" if adc == ads2 else "Unknown"
                print(f"Error setting up or reading AnalogIn for ADC {adc_id}, channel {channel}: {str(e)}")
                return None
        return None

    config = UNIT_CONFIGS[current_unit]
    for room, adc_config in config['adc'].items():
        adc = ads1 if adc_config['adc'] == 'ads1' else ads2
        analog_inputs[room] = setup_analog_in(adc, adc_config['channel'])

    adc_available = any(analog_inputs.values())
    print(f"ADC initialization {'successful' if adc_available else 'failed'}")

    # Print detailed status of each analog input
    print("\nDetailed ADC status:")
    for room, analog_in in analog_inputs.items():
        print(f"{room}: {'Connected' if analog_in else 'Failed'}")

    # Add more detailed debugging information
    for adc, name in [(ads1, "ADC1 (0x48)"), (ads2, "ADC2 (0x49)")]:
        if adc:
            print(f"\n{name} Debug Info:")
            print(f"  Data Rate: {adc.data_rate}")
            print(f"  Gain: {adc.gain}")
        else:
            print(f"\n{name} is not initialized")

# Set up Terminal for TUI
term = Terminal()

def get_sensor_data():
    data = []
    config = UNIT_CONFIGS[current_unit]
    
    # Monitor laser receivers
    for room, pins in config['lasers'].items():
        rx_status = GPIO.input(pins['LR'])
        status = f"Beam: {'Intact' if rx_status else 'Broken'}"
        data.append((f"{room} Laser", "Laser System", room, status))
        data.append((f"{room} Debug", "Laser Debug", room, f"TX GPIO: {pins['LT']}, RX GPIO: {pins['LR']}, RX Status: {rx_status}"))
    
    # Test ADCs
    current_time = time.time()
    for room, analog_in in analog_inputs.items():
        if analog_in is not None:
            try:
                value = analog_in.value
                voltage = analog_in.voltage
                
                # Calculate the change in voltage
                voltage_change = abs(voltage - filters.get(room, {}).get('last_voltage', voltage))
            
                if room in ['Gate', 'Cuddle Cross', 'Deep Playa Handshake']:  # Resistor ladder switches
                    button_status = get_button_status(voltage)
                    status = f"Value: {value}, Voltage: {voltage:.3f}V, {button_status}"
                else:  # Other sensors (including piezo)
                    knock_status = "No knock"
                    if voltage_change > DEBUG_THRESHOLD:
                        debug_status = f"Debug: Change detected: {voltage_change:.3f}V"
                        if voltage > KNOCK_THRESHOLD and voltage_change > VOLTAGE_CHANGE_THRESHOLD and current_time - filters.get(room, {}).get('last_knock', 0) > COOLDOWN_TIME:
                            knock_status = "KNOCK DETECTED"
                            filters.setdefault(room, {})['last_knock'] = current_time
                    else:
                        debug_status = ""
                
                    status = f"Value: {value}, Voltage: {voltage:.3f}V, Change: {voltage_change:.3f}V, {knock_status}"
                    if debug_status:
                        status += f", {debug_status}"
                
                filters.setdefault(room, {})['last_voltage'] = voltage
            except Exception as e:
                status = f"Reading failed: {str(e)}"
                print(f"Error reading {room}: {str(e)}")
        else:
            status = "Not initialized"
        data.append((room, "ADC", room, status))
    
    # Add ADC debug information
    for adc, name in [(ads1, "ADC1"), (ads2, "ADC2")]:
        if adc:
            try:
                data.append((f"{name} Debug", "Info", "All", f"Address: {'0x48' if name == 'ADC1' else '0x49'}, Data rate: {adc.data_rate}, Gain: {adc.gain}"))
            except Exception as e:
                data.append((f"{name} Debug", "Info", "All", f"Error: {str(e)}"))
        else:
            data.append((f"{name} Debug", "Info", "All", "ADC not initialized"))
    
    return data

def get_button_status(voltage):
    if voltage < 0.1:
        return "Error: Voltage too low"
    elif voltage < 0.4:
        return "Button 1 pressed"
    elif voltage < 0.7:
        return "Button 2 pressed"
    elif voltage < 1.0:
        return "Button 3 pressed"
    elif voltage < 1.3:
        return "Buttons 1 and 2 pressed"
    elif voltage < 1.6:
        return "Buttons 1 and 3 pressed"
    elif voltage < 1.9:
        return "Buttons 2 and 3 pressed"
    elif voltage < 2.2:
        return "All buttons pressed"
    else:
        return "No button pressed"

def display_tui():
    data = get_sensor_data()
    print(term.home + term.clear)
    print(term.move_y(0) + term.center(f"LoHP Maze Hardware Test - {UNIT_CONFIGS[current_unit]['name']}"))
    print(term.move_y(2) + term.center("Press 'q' to quit, 'b' for button test, 'u' to switch unit"))
    
    for i, (component, description, location, status) in enumerate(data):
        y = i + 4
        print(term.move_xy(0, y) + f"{component:<20} {description:<10} {location:<20} {status}")
    
    print(term.move_xy(0, term.height - 1))

def button_test():
    print(term.home + term.clear)
    print(term.move_y(0) + term.center("Button Test Mode"))
    print(term.move_y(2) + "Press each button one at a time. Press 'q' to quit.")
    
    button_values = {}
    last_value = 0
    debounce_time = 0.5  # 500ms debounce
    last_press_time = 0
    stable_count = 0
    stable_threshold = 10  # Number of stable readings required
    
    config = UNIT_CONFIGS[current_unit]
    resistor_ladder_room = next((room for room, adc_config in config['adc'].items() if room in ['Gate', 'Cuddle Cross', 'Deep Playa Handshake']), None)
    
    if not resistor_ladder_room or resistor_ladder_room not in analog_inputs:
        print(term.move_y(4) + "No resistor ladder found for this unit. Press any key to return.")
        term.inkey()
        return

    analog_in = analog_inputs[resistor_ladder_room]
    
    while True:
        adc_value = analog_in.value
        voltage = analog_in.voltage
        
        current_time = time.time()
        
        if abs(adc_value - last_value) > 100:
            stable_count = 0
        else:
            stable_count += 1
        
        if stable_count >= stable_threshold and (current_time - last_press_time) > debounce_time:
            # Detect stable ADC value and apply debounce
            rounded_adc = round(adc_value, -2)  # Round to nearest 100
            if rounded_adc not in [round(v[0], -2) for v in button_values.values()]:
                button_name = f"Button {len(button_values) + 1}"
                button_values[button_name] = (adc_value, voltage)
                print(term.move_y(6 + len(button_values)) + f"{button_name}: ADC Value = {adc_value}, Voltage = {voltage:.3f}V")
                last_press_time = current_time
        
        last_value = adc_value
        
        print(term.move_xy(0, 4) + f"Current ADC Value: {adc_value}, Voltage: {voltage:.3f}V" + " " * 20)
        
        key = term.inkey(timeout=0.1)
        if key == 'q':
            break
        elif key == 'r':
            button_values.clear()
            print(term.clear())
            print(term.move_y(0) + term.center("Button Test Mode"))
            print(term.move_y(2) + "Press each button one at a time. Press 'q' to quit. Press 'r' to reset.")
    
    print(term.move_y(6 + len(button_values) + 2) + "Button Test Complete. Press any key to return to main menu.")
    term.inkey()

def switch_unit():
    global current_unit
    units = list(UNIT_CONFIGS.keys())
    current_index = units.index(current_unit)
    next_index = (current_index + 1) % len(units)
    current_unit = units[next_index]
    print(f"Switched to {UNIT_CONFIGS[current_unit]['name']}")
    setup_gpio()
    initialize_adc()

try:
    setup_gpio()
    check_i2c_devices()
    initialize_adc()
    with term.cbreak(), term.hidden_cursor():
        while True:
            display_tui()
            key = term.inkey(timeout=0.1)
            if key == 'q':
                break
            elif key == 'b':
                button_test()
            elif key == 'u':
                switch_unit()
except KeyboardInterrupt:
    print("Program interrupted by user")
except Exception as e:
    print(f"Unexpected error: {str(e)}")
finally:
    GPIO.cleanup()
    print(term.clear())

# Call this function before initializing ADCs
check_i2c_devices()
