# Adding and Maintaining Effects in the LoHP-MazeManager Control System

This guide explains how to add new effects and maintain existing ones in the LoHP-MazeManager Control System.

## Adding a New Effect

1. Create a new Python file in the `effects/` directory:
   - Name it appropriately, e.g., `new_effect.py`.
   - Define a function that creates and returns the effect data.

2. Update `effects/__init__.py`:
   - Import the new effect creation function.

3. Update `effects_manager.py`:
   - Add the new effect to the `initialize_effects()` method.

4. (Optional) Update `api-examples.md`:
   - If your effect can be triggered via API, add an example of how to call it.

## Example: Adding a New "Strobe" Effect

1. Create `effects/strobe.py`:

```python
import logging

logger = logging.getLogger(__name__)

def create_strobe_effect():
    strobe_effect = {
        "duration": 5.0,
        "description": "Rapid flashing white light",
        "steps": []
    }
    for i in range(50):  # 50 flashes over 5 seconds
        t = i * 0.1
        strobe_effect["steps"].extend([
            {"time": t, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": t + 0.05, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ])
    logger.debug(f"Created Strobe effect: {strobe_effect}")
    logger.info(f"Strobe effect created with {len(strobe_effect['steps'])} steps over {strobe_effect['duration']} seconds")
    return strobe_effect
```

2. Update `effects/__init__.py`:

```python
from .strobe import create_strobe_effect
from .lightning_storm import create_lightning_storm_effect
```

3. In `effects_manager.py`, add to the `initialize_effects()` method:

```python
("Strobe", create_strobe_effect()),
```

4. In `api-examples.md`, add:

```markdown
## Trigger Strobe Effect

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Strobe"}'
```
```

## Maintaining Existing Effects

1. To modify an existing effect:
   - Locate the effect's file in the `effects/` directory.
   - Update the effect creation function as needed.
   - If you've changed the function name or file name, update `effects/__init__.py` accordingly.

2. If you've changed the effect's parameters or behavior significantly:
   - Update the `initialize_effects()` method in `effects_manager.py` if necessary.
   - Update the API documentation in `api-examples.md` if the usage has changed.

3. Always test your changes thoroughly to ensure they work as expected and don't interfere with other system functionalities.

## Best Practices

1. Keep each effect in its own file for better organization and maintainability.
2. Use descriptive names for effect files and functions.
3. Include detailed logging in your effect creation functions.
4. Document any special requirements or considerations for each effect in comments.
5. When updating effects, consider backwards compatibility with existing configurations.
6. Regularly review and optimize effects for performance.
7. Use the `effect_utils.py` file for common utility functions that can be shared across multiple effects.
8. When creating new effects, consider how they might interact with the theme system and ensure compatibility.

Remember to test all changes in a development environment before deploying to production. Use the `test_api.py` script to verify that new or modified effects work correctly with the API.
import RPi.GPIO as GPIO
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GPIO pin configurations
LASER_PINS = {
    'EntranceLT': 17,
    'EntranceLR': 27,
    'CuddleCrossLT': 22,
    'CuddleCrossLR': 5,
    'PhotoBombLT': 24,
    'PhotoBombLR': 6,
    'NoFriendsMondayLT': 25,
    'NoFriendsMondayLR': 13,
    'ExitLT': 19,
    'ExitLR': 26
}

BUTTON_PINS = {
    'EntranceButton': 23,
    'CuddleCrossButton': 18,
    'PhotoBombButton': 4,
    'NoFriendsMondayButton': 12,
    'ExitButton': 16
}

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    for pin in LASER_PINS.values():
        GPIO.setup(pin, GPIO.OUT)
    for pin in BUTTON_PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def test_lasers():
    logger.info("Testing lasers...")
    for name, pin in LASER_PINS.items():
        GPIO.output(pin, GPIO.HIGH)
        logger.info(f"{name} (Pin {pin}) ON")
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)
        logger.info(f"{name} (Pin {pin}) OFF")
        time.sleep(0.5)

def test_buttons():
    logger.info("Testing buttons... Press each button when prompted.")
    for name, pin in BUTTON_PINS.items():
        logger.info(f"Press the {name} (Pin {pin})")
        while GPIO.input(pin) == GPIO.HIGH:
            time.sleep(0.1)
        logger.info(f"{name} pressed successfully!")
        time.sleep(0.5)

def main():
    try:
        setup_gpio()
        test_lasers()
        test_buttons()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        GPIO.cleanup()
        logger.info("GPIO cleaned up")

if __name__ == "__main__":
    main()
