import json
import logging

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

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except IOError:
            logger.error(f"Error writing to {self.config_file}")
