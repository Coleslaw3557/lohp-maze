# LoHP-MazeManager Control System

## Overview

The LoHP-MazeManager Control System is a sophisticated lighting and audio control system designed for escape rooms and interactive experiences. It provides a centralized management interface for controlling lighting effects, audio playback, and synchronized events across multiple rooms.

## Features

- Real-time control of DMX lighting fixtures
- Audio playback and synchronization
- Theme-based lighting effects
- Custom effect creation and management
- Remote client support for distributed audio playback
- WebSocket-based communication for real-time updates
- RESTful API for integration with other systems

## System Requirements

- Python 3.7+
- FTDI-based DMX interface
- Network connectivity for remote clients

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/LoHP-MazeManager.git
   cd LoHP-MazeManager
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure the system:
   - Edit `light_config.json` to match your lighting setup
   - Edit `audio_config.json` to configure audio effects
   - Adjust other configuration files as needed

4. Start the server:
   ```
   python main.py
   ```

## Usage

The system can be controlled via the RESTful API or through custom integrations. For detailed API documentation, see [api-docs.md](api-docs.md).

### Basic Operations

1. Set a theme:
   ```
   curl -X POST http://localhost:5000/api/set_theme -H "Content-Type: application/json" -d '{"theme_name": "NeonNightlife"}'
   ```

2. Run an effect in a room:
   ```
   curl -X POST http://localhost:5000/api/run_effect -H "Content-Type: application/json" -d '{"room": "Entrance", "effect_name": "Lightning"}'
   ```

3. Adjust master brightness:
   ```
   curl -X POST http://localhost:5000/api/set_master_brightness -H "Content-Type: application/json" -d '{"brightness": 0.8}'
   ```

## Architecture

The system consists of several key components:

- `main.py`: The main server application
- `effects_manager.py`: Manages and applies lighting effects
- `theme_manager.py`: Handles theme-based lighting control
- `dmx_interface.py`: Interfaces with the DMX hardware
- `audio_manager.py`: Manages audio playback and synchronization
- `remote_host_manager.py`: Handles communication with remote clients

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers directly.
