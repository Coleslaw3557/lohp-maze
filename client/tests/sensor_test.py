import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal
from collections import deque

def test_level_shifter(input_pin, output_pin):
    GPIO.setup(input_pin, GPIO.OUT)
    
    for state in [GPIO.HIGH, GPIO.LOW]:
        GPIO.output(input_pin, state)
        time.sleep(0.1)
    
    GPIO.setup(input_pin, GPIO.IN)
    
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

# Call these functions to initialize I2C and ADCs
check_i2c_devices()
initialize_adc()

# Set up Terminal for TUI
term = Terminal()

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
        if analog_in is not None:
            try:
                value = analog_in.value
                voltage = analog_in.voltage
                status = f"Value: {value}, Voltage: {voltage:.2f}V"
            except Exception as e:
                status = f"Reading failed: {str(e)}"
                print(f"Error reading {adc} {channel}: {str(e)}")
        else:
            status = "Not initialized"
        data.append((adc, channel, room, status))
    
    # Add ADC debug information
    for adc, name in [(ads1, "ADC1"), (ads2, "ADC2")]:
        if adc:
            try:
                data.append((f"{name} Debug", "Info", "All", f"Address: 0x{adc.address:02X}, Data rate: {adc.data_rate}, Gain: {adc.gain}"))
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
    try:
        # Turn off all lasers
        for pin in laser_transmitters.values():
            if GPIO.gpio_function(pin) == GPIO.OUT:
                GPIO.output(pin, GPIO.LOW)
    except Exception as e:
        print(f"Error turning off lasers: {str(e)}")
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
