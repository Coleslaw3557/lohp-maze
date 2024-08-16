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

def initialize_adc():
    global adc_available, ads1, ads2, gate_resistor_ladder1, gate_resistor_ladder2, gate_buttons, porto_piezo1, porto_piezo2, porto_piezo3
    adc_available = False
    try:
        ads1 = ADS.ADS1115(i2c, address=0x48, gain=1)  # ADC1 for Gate Room
        ads1.data_rate = 8
        ads2 = ADS.ADS1115(i2c, address=0x49, gain=1)  # ADC2 for Porto Room
        ads2.data_rate = 8

        # Set up analog inputs
        gate_resistor_ladder1 = AnalogIn(ads1, ADS.P0)
        gate_resistor_ladder2 = AnalogIn(ads1, ADS.P1)
        gate_buttons = AnalogIn(ads1, ADS.P2)
        porto_piezo1 = AnalogIn(ads2, ADS.P0)
        porto_piezo2 = AnalogIn(ads2, ADS.P1)
        porto_piezo3 = AnalogIn(ads2, ADS.P2)
        
        adc_available = True
        print("ADC initialization successful")
    except Exception as e:
        print(f"ADC initialization failed: {str(e)}")

initialize_adc()

# Set up Terminal for TUI
term = Terminal()

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
            try:
                value = analog_in.value
                voltage = analog_in.voltage
                status = f"Value: {value}, Voltage: {voltage:.2f}V"
            except Exception as e:
                status = f"Reading failed: {str(e)}"
        else:
            status = "Offline"
        data.append((adc, channel, room, status))
    
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
    # Turn off all lasers
    for pin in laser_transmitters.values():
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print(term.clear())
