import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15.analog_in import AnalogIn

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

def check_laser_receivers():
    for room, pin in laser_receivers.items():
        if GPIO.input(pin) == GPIO.LOW:
            print(f"{room} laser beam intact.")
        else:
            print(f"{room} laser beam broken!")

def check_analog_sensors():
    print(f"Gate Resistor Ladder 1: {gate_resistor_ladder1.value}")
    print(f"Gate Resistor Ladder 2: {gate_resistor_ladder2.value}")
    print(f"Porto Piezo 1: {porto_piezo1.value}")
    print(f"Porto Piezo 2: {porto_piezo2.value}")
    print(f"Porto Piezo 3: {porto_piezo3.value}")

def test_laser_transmitters():
    for room, tx_pin in laser_transmitters.items():
        rx_pin = laser_receivers[room]
        print(f"\nTesting {room} laser:")
        
        # Turn off the laser
        GPIO.output(tx_pin, GPIO.LOW)
        time.sleep(0.5)
        if GPIO.input(rx_pin) == GPIO.HIGH:
            print(f"  {room} laser OFF test: PASSED")
        else:
            print(f"  {room} laser OFF test: FAILED")
        
        # Turn on the laser
        GPIO.output(tx_pin, GPIO.HIGH)
        time.sleep(0.5)
        if GPIO.input(rx_pin) == GPIO.LOW:
            print(f"  {room} laser ON test: PASSED")
        else:
            print(f"  {room} laser ON test: FAILED")

try:
    while True:
        print("\n--- Checking Sensors ---")
        check_laser_receivers()
        check_analog_sensors()
        
        print("\n--- Testing Laser Transmitters ---")
        test_laser_transmitters()
        
        time.sleep(5)

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    # Turn off all lasers
    for pin in laser_transmitters.values():
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
