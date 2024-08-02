# Legends of the Hidden Playa - Maze Control System

## Overview

This project is the control system for the interactive art maze of the Burning Man camp "Legends of the Hidden Playa". It manages the lighting and effects throughout the maze, providing a dynamic and immersive experience for participants.

## System Architecture

The system consists of several key components:

1. **Flask Web Application**: The main control interface and backend logic.
2. **DMX Interface**: Manages communication with the lighting fixtures.
3. **Light Configuration Manager**: Handles the setup and management of light models and room layouts.
4. **Effects Manager**: Controls the creation and execution of lighting effects and themes.

### Hardware Setup

- **Controller**: Raspberry Pi 4 (4GB RAM)
- **DMX Interface**: FTDI-based USB to DMX adapter
- **Lighting**: Various DMX-controlled LED fixtures (see `light_config.json` for specific models)
- **Network**: Local Wi-Fi network for control access

## Software Components

### 1. Flask Web Application (`main.py`)

The core of the control system, providing:
- Web-based user interface for managing rooms, light models, effects, and themes
- RESTful API endpoints for real-time control
- Integration of all other components

Key features:
- Dynamic theme management
- Real-time effect testing
- Global Hz (update frequency) control
- Verbose logging toggle

### 2. DMX Interface (`dmx_interface.py`)

Handles low-level communication with DMX fixtures:
- Uses pyftdi for FTDI chip communication
- Implements DMX512 protocol timing
- Provides thread-safe operations for concurrent access

Technical specs:
- DMX refresh rate: Up to 40Hz (configurable)
- 512 DMX channels supported
- Automatic error recovery and port management

### 3. Light Configuration Manager (`light_config_manager.py`)

Manages the physical layout and configuration of lights:
- JSON-based configuration storage (`light_config.json`)
- Dynamic management of room layouts and light models
- Provides an abstraction layer between logical rooms and physical DMX addresses

### 4. Effects Manager (`effects_manager.py`)

Handles the creation, storage, and execution of lighting effects and themes:
- JSON-based effect and theme storage
- Real-time theme generation and execution
- Supports complex, multi-room lighting sequences

## Key Files

- `main.py`: Main Flask application and control logic
- `dmx_interface.py`: DMX communication layer
- `light_config_manager.py`: Light and room configuration management
- `effects_manager.py`: Effect and theme management
- `light_config.json`: Configuration file for light models and room layouts
- `effects_config.json`: Storage for custom effects
- `requirements.txt`: Python dependencies
- `Dockerfile` and `docker-compose.yml`: Containerization setup

## Setup and Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `light_config.json` with your specific light models and room layout
4. Run the application: `python main.py`

For containerized deployment:
```bash
docker-compose up --build
```

## Usage

Access the web interface at `http://<controller-ip>:5000`

Key functionalities:
- Room Manager: Add, edit, and remove rooms
- Light Models: Manage different types of lighting fixtures
- Effects: Create and edit lighting effects
- Themes: Design and control overarching lighting themes
- Test Mode: Real-time testing of individual fixtures and effects

## Technical Considerations

- The system uses a fixed 40Hz update rate for DMX communication to ensure smooth transitions and effects.
- Thread-safe operations are implemented throughout to handle concurrent access to the DMX interface.
- The Effects Manager uses a sophisticated algorithm to generate dynamic themes based on parameters like color variation, intensity fluctuation, and overall brightness.
- Error handling and logging are implemented at multiple levels for robust operation and debugging.

## Future Enhancements

- Integration with external sensors for interactive effects
- Mobile app for remote control
- Machine learning-based theme generation
- Audio synchronization for music-reactive lighting

## Contributing

Contributions to the Legends of the Hidden Playa maze control system are welcome. Please submit pull requests or open issues for bugs, feature requests, or improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
