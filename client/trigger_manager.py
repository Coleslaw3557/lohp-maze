import asyncio
import logging
import time
import random
import board
import busio
import RPi.GPIO as GPIO
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import aiohttp

logger = logging.getLogger(__name__)

BUTTON_PRESSED_VOLTAGE = 0.1   # below this the button is pressed (pulls to ground)
BUTTON_RELEASED_VOLTAGE = 3.0  # above this the button is released
DEFAULT_PIEZO_THRESHOLD = 2.0


class TriggerManager:
    def __init__(self, config):
        self.config = config
        self.associated_rooms = config.get('associated_rooms', [])
        self.triggers = [t for t in config.get('triggers', [])
                         if not t.get('room') or t.get('room') in self.associated_rooms]
        self.server_ip = config.get('server_ip')
        self.start_time = time.time()
        self.startup_delay = config.get('startup_delay', 10)
        self.cooldown_period = config.get('cooldown_period', 5)
        self.trigger_cooldowns = {}  # trigger name -> last fire time
        self.laser_states = {}       # trigger name -> last rx pin state
        self.button_pressed = {}     # trigger name -> currently held down
        self.adc_channels = {}       # trigger name -> AnalogIn
        self.piezo_attempts = 0
        self.piezo_settings = config.get('piezo_settings', {
            'attempts_required': 3,
            'correct_answer_probability': 0.25
        })

        GPIO.setmode(GPIO.BCM)
        for trigger in self.triggers:
            logger.info(f"Trigger: {trigger['name']}, Type: {trigger['type']}")
            if trigger['type'] == 'laser':
                GPIO.setup(trigger['tx_pin'], GPIO.OUT)
                GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Laser on
                GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self.laser_states[trigger['name']] = GPIO.input(trigger['rx_pin'])

    async def setup(self):
        """Initialize the ADS1115 channels for adc (button) and piezo triggers."""
        adc_triggers = [t for t in self.triggers if t['type'] in ('adc', 'piezo')]
        if not adc_triggers:
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            ads_devices = {}
            for trigger in adc_triggers:
                channel = trigger.get('channel')
                if channel is None:
                    logger.error(f"No channel specified for trigger: {trigger['name']}. Skipping.")
                    continue
                address = trigger.get('adc_address', '0x48')
                if address not in ads_devices:
                    ads_devices[address] = ADS.ADS1115(i2c, address=int(address, 16))
                self.adc_channels[trigger['name']] = AnalogIn(ads_devices[address], getattr(ADS, f'P{channel}'))

            await asyncio.sleep(2)  # Let readings stabilize
            for name, channel in self.adc_channels.items():
                logger.info(f"Initial ADC reading for {name}: {channel.voltage:.3f}V")
        except Exception as e:
            logger.error(f"Error setting up ADC: {e}")
            self.adc_channels = {}

    async def monitor_triggers(self):
        """Single polling loop for all trigger types. Fires actions without blocking the loop."""
        tick = 0
        while True:
            now = time.time()
            if now - self.start_time >= self.startup_delay:
                for trigger in self.triggers:
                    try:
                        if trigger['type'] == 'laser':
                            self._check_laser(trigger, now)
                        elif tick % 5 == 0 and trigger['type'] in ('adc', 'piezo'):
                            self._check_adc(trigger, now)
                    except Exception as e:
                        logger.error(f"Error checking trigger {trigger['name']}: {e}")
            tick += 1
            await asyncio.sleep(0.01)  # Lasers every 10ms, ADC every 50ms

    def _check_laser(self, trigger, now):
        rx_state = GPIO.input(trigger['rx_pin'])
        name = trigger['name']
        previous_state = self.laser_states.get(name, rx_state)
        self.laser_states[name] = rx_state

        if previous_state == GPIO.HIGH and rx_state == GPIO.LOW:  # Beam just broken
            if self._cooldown_passed(name, now):
                logger.info(f"Laser beam broken: {name}")
                self.trigger_cooldowns[name] = now
                self.fire(trigger)
        elif previous_state == GPIO.LOW and rx_state == GPIO.HIGH:
            logger.info(f"Laser beam restored: {name}")

    def _check_adc(self, trigger, now):
        channel = self.adc_channels.get(trigger['name'])
        if channel is None:
            return
        voltage = channel.voltage
        if trigger['type'] == 'adc':
            self._check_button(trigger, voltage)
        else:
            self._check_piezo(trigger, voltage, now)

    def _check_button(self, trigger, voltage):
        name = trigger['name']
        if voltage < BUTTON_PRESSED_VOLTAGE and not self.button_pressed.get(name):
            self.button_pressed[name] = True
            logger.info(f"Button pressed: {name}")
            self.fire(trigger)
        elif voltage > BUTTON_RELEASED_VOLTAGE:
            self.button_pressed[name] = False

    def _check_piezo(self, trigger, voltage, now):
        name = trigger['name']
        if voltage <= trigger.get('threshold', DEFAULT_PIEZO_THRESHOLD):
            return
        if not self._cooldown_passed(name, now):
            return
        self.trigger_cooldowns[name] = now
        self.piezo_attempts += 1
        logger.info(f"Piezo triggered: {name} (attempt {self.piezo_attempts})")

        if self.piezo_attempts >= self.piezo_settings['attempts_required']:
            self.piezo_attempts = 0
            if random.random() < self.piezo_settings['correct_answer_probability']:
                effect_name = "CorrectAnswer"
            else:
                effect_name = "WrongAnswer"
        else:
            effect_name = "WrongAnswer"
        self.fire(trigger, effect_override=effect_name)

    def _cooldown_passed(self, name, now):
        return now - self.trigger_cooldowns.get(name, 0) > self.cooldown_period

    def fire(self, trigger, effect_override=None):
        """Fire a trigger's action in the background so polling never blocks."""
        asyncio.create_task(self._fire(trigger, effect_override))

    async def _fire(self, trigger, effect_override=None):
        action = trigger.get('action')
        if not action or action.get('type') != 'curl':
            logger.error(f"No usable action defined for trigger: {trigger['name']}")
            return

        url = action['url'].replace('${server_ip}', self.server_ip)
        data = dict(action.get('data', {}))
        if effect_override:
            data['effect_name'] = effect_override

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(action['method'], url, json=data,
                                               timeout=aiohttp.ClientTimeout(total=30)) as response:
                        body = await response.text()
                        if response.status == 200:
                            logger.info(f"Triggered action for {trigger['name']}: {body}")
                        else:
                            logger.warning(f"Action for {trigger['name']} returned {response.status}: {body}")
                        return  # The server answered; don't re-fire the effect by retrying
            except asyncio.TimeoutError:
                logger.error(f"Timeout firing action for {trigger['name']}; not retrying")
                return  # The server may still be running the effect
            except aiohttp.ClientError as e:
                logger.error(f"Network error firing {trigger['name']}: {e} (attempt {attempt + 1}/3)")
                await asyncio.sleep(2 ** attempt)
        logger.error(f"Failed to fire action for {trigger['name']} after 3 attempts")

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
