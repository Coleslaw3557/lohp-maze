import logging

from effect_utils import JADE, create_flash_effect

logger = logging.getLogger(__name__)


def create_correct_answer_effect():
    # Accent-par chirp: in two-fixture rooms the room's ambiance keeps playing
    # on the other par while this answers the button.
    effect = create_flash_effect(
        "Three quick jade flashes on the reaction par — a correct answer",
        JADE, flashes=3, period=0.5, hold=0.25, duration=2.0,
        fixture_role="accent")
    logger.info(f"Correct Answer effect created with {len(effect['steps'])} steps "
                f"over {effect['duration']} seconds")
    return effect
