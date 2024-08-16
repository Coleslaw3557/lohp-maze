import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal
from collections import deque

# Constants for knock detection
KNOCK_THRESHOLD = 0.1  # Adjust this value based on your piezo sensitivity
COOLDOWN_TIME = 0.5  # Cooldown time between knocks (in seconds)

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
    
    for pin in laser_transmitters.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # Turn on all lasers

    for pin in laser_receivers.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Use pull-down resistor

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

# Set up I2C for ADS1115
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)  # Lower the I2C frequency to 100 kHz
# Set up ADCs and analog inputs
adc_available = False
ads1 = None
ads2 = None
gate_resistor_ladder1 = gate_resistor_ladder2 = gate_buttons = None
porto_piezo1 = porto_piezo2 = porto_piezo3 = None
filters = {}
CONNECTED_THRESHOLD = 100

def check_i2c_devices():
    print("Checking I2C devices...")
    try:
        import subprocess
        result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error checking I2C devices: {str(e)}")

def initialize_adc():
    global adc_available, ads1, ads2, gate_resistor_ladder1, gate_resistor_ladder2, gate_buttons, porto_piezo1, porto_piezo2, porto_piezo3
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

    gate_resistor_ladder1 = setup_analog_in(ads1, ADS.P0)
    gate_resistor_ladder2 = setup_analog_in(ads1, ADS.P1)
    gate_buttons = setup_analog_in(ads1, ADS.P2)
    porto_piezo1 = setup_analog_in(ads2, ADS.P0)
    porto_piezo2 = setup_analog_in(ads2, ADS.P1)
    porto_piezo3 = setup_analog_in(ads2, ADS.P2)

    adc_available = any([gate_resistor_ladder1, gate_resistor_ladder2, gate_buttons, porto_piezo1, porto_piezo2, porto_piezo3])
    print(f"ADC initialization {'successful' if adc_available else 'failed'}")

    # Print detailed status of each analog input
    print("\nDetailed ADC status:")
    print(f"ADC1 (0x48) - Gate Room:")
    print(f"  Resistor Ladder 1 (A0): {'Connected' if gate_resistor_ladder1 else 'Failed'}")
    print(f"  Resistor Ladder 2 (A1): {'Connected' if gate_resistor_ladder2 else 'Failed'}")
    print(f"  Buttons (A2): {'Connected' if gate_buttons else 'Failed'}")
    print(f"ADC2 (0x49) - Porto Room:")
    print(f"  Piezo 1 (A0): {'Connected' if porto_piezo1 else 'Failed'}")
    print(f"  Piezo 2 (A1): {'Connected' if porto_piezo2 else 'Failed'}")
    print(f"  Piezo 3 (A2): {'Connected' if porto_piezo3 else 'Failed'}")

    # Add more detailed debugging information
    if ads1:
        print(f"\nADC1 (0x48) Debug Info:")
        print(f"  Address: 0x48")
        print(f"  Data Rate: {ads1.data_rate}")
        print(f"  Gain: {ads1.gain}")
    else:
        print("\nADC1 (0x48) is not initialized")

    if ads2:
        print(f"\nADC2 (0x49) Debug Info:")
        print(f"  Address: 0x49")
        print(f"  Data Rate: {ads2.data_rate}")
        print(f"  Gain: {ads2.gain}")
    else:
        print("\nADC2 (0x49) is not initialized")

# Call these functions to initialize I2C and ADCs
check_i2c_devices()
initialize_adc()

# Set up Terminal for TUI
term = Terminal()

# Initialize filters for knock detection
filters = {
    "ADC2 A0": {'last_voltage': 0, 'last_knock': 0},
    "ADC2 A1": {'last_voltage': 0, 'last_knock': 0},
    "ADC2 A2": {'last_voltage': 0, 'last_knock': 0}
}

def check_i2c_devices():
    print("Checking I2C devices...")
    try:
        import subprocess
        result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error checking I2C devices: {str(e)}")

def get_sensor_data():
    data = []
    
    # Monitor laser receivers
    for room, rx_pin in laser_receivers.items():
        tx_pin = laser_transmitters[room]
        
        # Read receiver status
        rx_status = GPIO.input(rx_pin)
        
        status = f"Beam: {'Intact' if rx_status else 'Broken'}"
        data.append((f"{room} Laser", "Laser System", room, status))
        
        # Add debug information
        data.append((f"{room} Debug", "Laser Debug", room, f"TX GPIO: {tx_pin}, RX GPIO: {rx_pin}, RX Status: {rx_status}"))
    
    # Test ADCs
    adc_data = [
        ("ADC1 A0", "Channel 0", "Gate", gate_resistor_ladder1),
        ("ADC1 A1", "Channel 1", "Gate", gate_resistor_ladder2),
        ("ADC1 A2", "Channel 2", "Gate", gate_buttons),
        ("ADC2 A0", "Channel 0", "Porto", porto_piezo1),
        ("ADC2 A1", "Channel 1", "Porto", porto_piezo2),
        ("ADC2 A2", "Channel 2", "Porto", porto_piezo3)
    ]
    
    current_time = time.time()
    for adc, channel, room, analog_in in adc_data:
        if analog_in is not None:
            try:
                value = analog_in.value
                voltage = analog_in.voltage
                
                # Knock detection for piezo sensors
                if room == "Porto":
                    if voltage > KNOCK_THRESHOLD and current_time - filters[adc].get('last_knock', 0) > COOLDOWN_TIME:
                        knock_status = "KNOCK DETECTED"
                        filters[adc]['last_knock'] = current_time
                    else:
                        knock_status = "No knock"
                    
                    # Calculate and display the change in voltage
                    voltage_change = voltage - filters[adc].get('last_voltage', voltage)
                    filters[adc]['last_voltage'] = voltage
                    
                    status = f"Value: {value}, Voltage: {voltage:.3f}V, Change: {voltage_change:.3f}V, {knock_status}"
                else:
                    status = f"Value: {value}, Voltage: {voltage:.3f}V"
            except Exception as e:
                status = f"Reading failed: {str(e)}"
                print(f"Error reading {adc} {channel}: {str(e)}")
        else:
            status = "Not initialized"
        data.append((adc, channel, room, status))
    
    # Add ADC debug information
    for adc, name, address in [(ads1, "ADC1", "0x48"), (ads2, "ADC2", "0x49")]:
        if adc:
            try:
                data.append((f"{name} Debug", "Info", "All", f"Address: {address}, Data rate: {adc.data_rate}, Gain: {adc.gain}"))
            except Exception as e:
                data.append((f"{name} Debug", "Info", "All", f"Error: {str(e)}"))
        else:
            data.append((f"{name} Debug", "Info", "All", "ADC not initialized"))
    
    return data

def display_tui():
    data = get_sensor_data()
    print(term.home + term.clear)
    print(term.move_y(0) + term.center("LoHP Maze Hardware Test"))
    print(term.move_y(2) + term.center("Press 'q' to quit"))
    
    for i, (component, description, location, status) in enumerate(data):
        y = i + 4
        print(term.move_xy(0, y) + f"{component:<10} {description:<20} {location:<15} {status}")
    
    print(term.move_xy(0, term.height - 1))

try:
    setup_gpio()  # Ensure GPIO is set up before the main loop
    check_i2c_devices()  # Check I2C devices
    initialize_adc()  # Initialize ADCs
    with term.cbreak(), term.hidden_cursor():
        display_tui()  # Initial display
        while True:
            key = term.inkey(timeout=0.1)
            if key == 'q':
                break
            try:
                display_tui()
            except Exception as e:
                print(f"Error in display_tui: {str(e)}")
                time.sleep(1)  # Wait a bit before trying again

except KeyboardInterrupt:
    print("Program interrupted by user")
except Exception as e:
    print(f"Unexpected error: {str(e)}")
finally:
    GPIO.cleanup()
    print(term.clear())
def check_i2c_devices():
    print("Checking I2C devices...")
    try:
        import subprocess
        result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error checking I2C devices: {str(e)}")

# Call this function before initializing ADCs
check_i2c_devices()
