import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal

# Constants
CONNECTED_THRESHOLD = 0.3
BUTTON_DEBOUNCE_TIME = 0.1

# Unit A Configuration
UNIT_A_CONFIG = {
    'name': 'UNIT-A',
    'lasers': {
        'Entrance': {'LT': 4, 'LR': 17},
        'Cuddle Cross': {'LT': 18, 'LR': 27},
        'Photo Bomb': {'LT': 22, 'LR': 23},
        'No Friends Monday': {'LT': 24, 'LR': 25},
        'Exit': {'LT': 5, 'LR': 6}
    },
    'adc': {
        'Cuddle Cross': {
            'adc': 'ads1',
            'channels': {
                'Button 1': ADS.P0,
                'Button 2': ADS.P1,
                'Button 3': ADS.P2,
                'Button 4': ADS.P3
            }
        }
    }
}

# Initialize current unit
current_unit = UNIT_A_CONFIG

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    for room, pins in current_unit['lasers'].items():
        GPIO.setup(pins['LT'], GPIO.OUT)
        GPIO.output(pins['LT'], GPIO.HIGH)  # Turn on all lasers initially
        GPIO.setup(pins['LR'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Use pull-down resistor
        print(f"Setting up {room} laser: LT (GPIO {pins['LT']}) set to HIGH, LR (GPIO {pins['LR']}) set as INPUT")
    
    print("GPIO setup complete")

# Set up GPIO
setup_gpio()
print("GPIO setup complete")

# Set up I2C for ADS1115
i2c = busio.I2C(board.SCL, board.SDA)
ads1 = ADS.ADS1115(i2c, address=0x48)

# Set up analog input for button testing
analog_input = AnalogIn(ads1, ADS.P0)

# Set up Terminal for TUI
term = Terminal()

def get_sensor_data():
    data = []
    
    # Monitor laser receivers
    for room, pins in current_unit['lasers'].items():
        rx_status = GPIO.input(pins['LR'])
        tx_status = GPIO.input(pins['LT'])
        status = f"Beam: {'Broken' if rx_status else 'Intact'}"  # Inverted logic
        tx_state = f"TX: {'ON' if tx_status else 'OFF'}"
        raw_status = f"Raw RX: {'HIGH' if rx_status else 'LOW'}"
        data.append((f"{room} Laser", "Laser System", room, f"{status}, {tx_state}, {raw_status}"))
    
    # Test ADC for button presses
    for button, channel in current_unit['adc']['Cuddle Cross']['channels'].items():
        analog_input = AnalogIn(ads1, channel)
        value = analog_input.value
        voltage = analog_input.voltage
        button_status = get_button_status(voltage)
        data.append((f"Cuddle Cross {button}", "ADC", "Cuddle Cross", f"Value: {value}, Voltage: {voltage:.3f}V, {button_status}"))
    
    return data

def get_button_status(voltage):
    if voltage < 0.1:
        return "Button pressed"
    elif voltage > 0.9:
        return "Button not pressed"
    else:
        return "Error: Voltage in undefined range"

def toggle_laser(room):
    pins = current_unit['lasers'][room]
    current_state = GPIO.input(pins['LT'])
    new_state = not current_state
    GPIO.output(pins['LT'], GPIO.HIGH if new_state else GPIO.LOW)
    return f"{room} laser {'turned ON' if new_state else 'turned OFF'}"

def display_tui():
    data = get_sensor_data()
    print(term.home + term.clear)
    print(term.move_y(0) + term.center(f"LoHP Maze Hardware Test - {UNIT_A_CONFIG['name']}"))
    print(term.move_y(2) + term.center("Press 'q' to quit, 'b' for button test, '1'-'5' to toggle lasers"))
    
    for i, (component, description, location, status) in enumerate(data):
        y = i + 4
        print(term.move_xy(0, y) + f"{component:<20} {description:<10} {location:<20} {status}")
    
    print(term.move_y(len(data) + 5) + term.center("Laser Control: 1=Entrance, 2=Cuddle Cross, 3=Photo Bomb, 4=No Friends Monday, 5=Exit"))

def button_test():
    print(term.home + term.clear)
    print(term.move_y(0) + term.center("Button Test Mode"))
    print(term.move_y(2) + "Press each button one at a time. Press 'q' to quit.")
    
    button_values = {}
    last_press_time = 0
    
    while True:
        value = analog_input.value
        voltage = analog_input.voltage
        
        current_time = time.time()
        
        if (current_time - last_press_time) > BUTTON_DEBOUNCE_TIME:
            button_status = get_button_status(voltage)
            if button_status.startswith("Button") and button_status not in button_values:
                button_values[button_status] = (value, voltage)
                print(term.move_y(4 + len(button_values)) + f"{button_status}: ADC Value = {value}, Voltage = {voltage:.3f}V")
                last_press_time = current_time
        
        print(term.move_xy(0, 4) + f"Current ADC Value: {value}, Voltage: {voltage:.3f}V" + " " * 20)
        
        key = term.inkey(timeout=0.1)
        if key == 'q':
            break
    
    print(term.move_y(10) + "Button Test Complete. Press any key to return to main menu.")
    term.inkey()

try:
    with term.cbreak(), term.hidden_cursor():
        while True:
            display_tui()
            key = term.inkey(timeout=0.1)
            if key == 'q':
                break
            elif key == 'b':
                button_test()
            elif key in ['1', '2', '3', '4', '5']:
                room_index = int(key) - 1
                room = list(current_unit['lasers'].keys())[room_index]
                result = toggle_laser(room)
                print(term.move_y(term.height - 1) + term.center(result))
                time.sleep(1)  # Show the result for 1 second
            time.sleep(0.1)  # Add a small delay to prevent too rapid GPIO reading
except KeyboardInterrupt:
    print("Program interrupted by user")
except Exception as e:
    print(f"Unexpected error: {str(e)}")
finally:
    GPIO.cleanup()
    print(term.clear())
