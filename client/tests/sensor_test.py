import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from blessed import Terminal

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
ads1 = ADS.ADS1115(i2c, address=0x48)  # ADC1 for Gate Room
ads2 = ADS.ADS1115(i2c, address=0x49)  # ADC2 for Porto Room

# Set up analog inputs
gate_resistor_ladder1 = AnalogIn(ads1, ADS.P0)
gate_resistor_ladder2 = AnalogIn(ads1, ADS.P1)
porto_piezo1 = AnalogIn(ads2, ADS.P0)
porto_piezo2 = AnalogIn(ads2, ADS.P1)
porto_piezo3 = AnalogIn(ads2, ADS.P2)

# Set up Terminal for TUI
term = Terminal()

def get_sensor_data():
    data = []
    for room, pin in laser_receivers.items():
        status = "Intact" if GPIO.input(pin) == GPIO.LOW else "Broken"
        data.append((f"GPIO {pin}", f"{room} Laser", room, status))
    
    data.append(("ADC1 A0", "Resistor Ladder 1", "Gate", gate_resistor_ladder1.value))
    data.append(("ADC1 A1", "Resistor Ladder 2", "Gate", gate_resistor_ladder2.value))
    data.append(("ADC2 A0", "Piezo 1", "Porto", porto_piezo1.value))
    data.append(("ADC2 A1", "Piezo 2", "Porto", porto_piezo2.value))
    data.append(("ADC2 A2", "Piezo 3", "Porto", porto_piezo3.value))
    
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
