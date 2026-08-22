import logging

from effect_utils import JADE, create_flash_effect

logger = logging.getLogger(__name__)


def create_photobomb_landed_effect():
    # Photo-landed confirmation, LIGHTS-ONLY (2026-08-22, Tim): the audible
    # camera snap moved INTO the node's firmware and plays at the press edge
    # (photo-bomb.yaml snap extend) — streaming it from the Pi put the click
    # ~3s behind the flash. Same jade accent chirp as CorrectAnswer, under a
    # name with no audio_config pool, so nothing streams and nothing
    # double-clicks.
    effect = create_flash_effect(
        "Three quick jade flashes on the reaction par — photo landed "
        "(lights-only: the snap sound lives on the node)",
        JADE, flashes=3, period=0.5, hold=0.25, duration=2.0,
        fixture_role="accent")
    logger.info(f"PhotoBomb-Landed effect created with {len(effect['steps'])} "
                f"steps over {effect['duration']} seconds")
    return effect
