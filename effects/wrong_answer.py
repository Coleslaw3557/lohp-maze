import logging

from effect_utils import create_flash_effect

logger = logging.getLogger(__name__)


def create_wrong_answer_effect():
    # Accent-par chirp, same shape as CorrectAnswer in warning red.
    effect = create_flash_effect(
        "Three quick red flashes on the reaction par — a wrong answer",
        (255, 0, 0), flashes=3, period=0.5, hold=0.25, duration=1.5,
        fixture_role="accent")
    logger.info(f"Wrong Answer effect created with {len(effect['steps'])} steps "
                f"over {effect['duration']} seconds")
    return effect
