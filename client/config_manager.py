import json
import logging
import os

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config_content = f.read()
            config = json.loads(config_content)
            config = self.replace_env_vars(config)
            # Multi-zone configs list rooms per zone; derive the flat room list from them
            if config.get('zones'):
                zone_rooms = sorted({
                    room for zone in config['zones'].values() for room in zone.get('rooms', [])
                })
                if not config.get('associated_rooms'):
                    config['associated_rooms'] = zone_rooms
                else:
                    uncovered = set(config['associated_rooms']) - set(zone_rooms)
                    if uncovered:
                        logger.warning(f"associated_rooms not covered by any zone "
                                       f"(their audio will be dropped): {sorted(uncovered)}")
            logger.info(f"Configuration loaded from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.config_file}: {str(e)}")
            logger.error(f"Content of {self.config_file}:")
            logger.error(config_content)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading config from {self.config_file}: {str(e)}")
            return {}

    def get(self, key, default=None):
        return self.config.get(key, default)

    def replace_env_vars(self, config):
        if isinstance(config, dict):
            return {k: self.replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self.replace_env_vars(v) for v in config]
        elif isinstance(config, str):
            if config.startswith('${') and config.endswith('}'):
                env_var = config[2:-1]
                return os.environ.get(env_var, config)
            return config
        else:
            return config
