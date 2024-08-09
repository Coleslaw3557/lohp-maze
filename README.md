# Legends of the Hidden Playa - Maze Control System

## Overview

This project is the control system for the interactive art maze of the Burning Man camp "Legends of the Hidden Playa". It manages the lighting and effects throughout the maze, providing a dynamic and immersive experience for participants.

## System Architecture

The system consists of several key components:

1. **Flask Web Application**: The main control interface and backend logic.
2. **DMX Interface**: Manages communication with the lighting fixtures.
3. **Light Configuration Manager**: Handles the setup and management of light models and room layouts.
4. **Effects Manager**: Controls the creation and execution of lighting effects and themes.
5. **Interrupt Handler**: Manages interruptions for specific fixtures and coordinates transitions.
6. **DMX State Manager**: Maintains the current state of all DMX channels and provides thread-safe access.

### Hardware Setup

- **DMX Interface**: FTDI-based USB to DMX adapter
- **Lighting**: Various DMX-controlled LED fixtures (see `light_config.json` for specific models)

## Software Components

### 1. Flask Web Application (`main.py`)

The core of the control system, providing:
- RESTful API endpoints for real-time control
- Integration of all other components

Key features:
- Dynamic theme management
- Real-time effect testing
- Master brightness control
- Interrupt system for specific fixture control

### 2. DMX Interface (`dmx_interface.py`)

Handles low-level communication with DMX fixtures:
- Uses pyftdi for FTDI chip communication
- Implements DMX512 protocol timing
- Provides thread-safe operations for concurrent access

Technical specs:
- DMX refresh rate: 44Hz (fixed as per DMX512 standard)
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
- Integrates with the Interrupt Handler for seamless effect transitions
- Implements master brightness control
- Supports both asynchronous and synchronous effect execution

### 5. Interrupt Handler (`interrupt_handler.py`)

Manages interruptions for specific fixtures:
- Coordinates transitions between main sequence and interrupted states
- Allows for precise control of individual fixtures during effects
- Supports both asynchronous and synchronous interruption methods

### 6. DMX State Manager (`dmx_state_manager.py`)

Maintains the current state of all DMX channels:
- Provides thread-safe access to channel values
- Implements locking mechanism to prevent race conditions

## Key Files

- `main.py`: Main Flask application and control logic
- `dmx_interface.py`: DMX communication layer
- `light_config_manager.py`: Light and room configuration management
- `effects_manager.py`: Effect and theme management
- `interrupt_handler.py`: Manages fixture interruptions
- `dmx_state_manager.py`: Maintains DMX channel states
- `light_config.json`: Configuration file for light models and room layouts

## Setup and Installation

1. Install dependencies: `pip install -r requirements.txt`
2. Configure `light_config.json` with your specific light models and room layout
3. Run the application: `python main.py`

## Usage

Access the API endpoints at `http://localhost:5000`

Key functionalities:
- Effects: Create and trigger lighting effects (both asynchronously and synchronously)
- Themes: Set and control overarching lighting themes
- Test Mode: Real-time testing of individual fixtures and effects
- Synchronous Effect Execution: Run effects in a blocking manner for precise timing control

### API Examples

For a comprehensive list of API examples, please refer to the `api-examples.md` file in the project root directory. This file contains detailed examples of how to use each API endpoint, including:

- Retrieving room layouts
- Listing available effects and themes
- Setting themes
- Running effects in specific rooms
- Adjusting master brightness
- Triggering special effects like lightning

To view the API examples:

```bash
cat api-examples.md
```

For the most up-to-date API documentation, always refer to the `api-examples.md` file.

### Docker Usage

To run the application using Docker:

1. Ensure Docker and Docker Compose are installed on your system.
2. Navigate to the project root directory.
3. Build and start the containers:

```bash
docker-compose up --build
```

This will start the application and make it accessible at `http://localhost:5000`.

## Technical Considerations

- The system uses a fixed 44Hz update rate for DMX communication to ensure smooth transitions and effects.
- Thread-safe operations are implemented throughout to handle concurrent access to the DMX interface and state management.
- The Effects Manager uses a sophisticated algorithm to generate dynamic themes based on parameters like color variation, intensity fluctuation, and overall brightness.
- The Interrupt Handler allows for precise control of individual fixtures without disrupting the overall lighting sequence, supporting both asynchronous and synchronous interruption methods.
- Error handling and logging are implemented at multiple levels for robust operation and debugging.
- Master brightness control affects all lighting outputs, allowing for global intensity adjustment without altering individual effect or theme designs.
# DMX Lighting Control System

This project is a comprehensive DMX lighting control system designed for managing complex lighting setups in various environments, such as escape rooms or interactive installations.

## Table of Contents

1. [System Overview](#system-overview)
2. [Components](#components)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [API Endpoints](#api-endpoints)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

## System Overview

The DMX Lighting Control System is built using Python and Flask, providing a robust backend for managing DMX fixtures, effects, themes, and room layouts. It uses the FTDI library for DMX output and supports various lighting models and effects.

## Components

1. **DMX State Manager**: Manages the current state of all DMX fixtures.
2. **DMX Output Manager**: Handles the output of DMX data to the physical fixtures.
3. **Light Config Manager**: Manages the configuration of light models and room layouts.
4. **Effects Manager**: Handles the creation and application of lighting effects and themes.
5. **Interrupt Handler**: Manages interruptions for applying effects to specific fixtures or rooms.
6. **Sequence Runner**: Runs sequences of lighting changes.
7. **Flask API**: Provides HTTP endpoints for controlling the system.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-repo/dmx-lighting-control.git
   cd dmx-lighting-control
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up the FTDI drivers for your system (refer to the FTDI documentation).

## Configuration

1. Edit `light_config.json` to set up your light models and room layout.
2. Adjust `effects_config.json` to define custom effects (if needed).
3. Set environment variables:
   - `DEBUG`: Set to 'True' for verbose logging (default: 'False')
   - `SECRET_KEY`: Set a secret key for Flask (default: 'your_secret_key_here')

## Usage

1. Start the server:
   ```
   python main.py
   ```

2. The server will start on `http://0.0.0.0:5000`.

3. Use the API endpoints to control the lighting system.

## API Endpoints

- `GET /api/rooms`: Get all configured rooms
- `GET /api/effects`: Get all available effects
- `GET /api/themes`: Get all available themes
- `GET /api/light_models`: Get all configured light models
- `POST /api/set_theme`: Set the current theme
- `POST /api/run_effect`: Run an effect in a specific room
- `POST /api/set_master_brightness`: Set the master brightness
- `POST /api/run_test`: Run a channel or effect test
- `POST /api/stop_test`: Stop the current test and reset lights
- `POST /api/run_effect_all_rooms`: Run an effect in all rooms

For detailed API usage, refer to the `api-examples.md` file.

## Testing

1. Use the `test_api.py` script to run automated tests:
   ```
   python test_api.py
   ```

2. Use the web interface (if available) to manually test effects and themes.

## Troubleshooting

- Check the logs for detailed error messages.
- Ensure the FTDI device is properly connected and recognized by the system.
- Verify that the DMX addresses in `light_config.json` match your physical setup.
- If effects are not working as expected, double-check the effect definitions in the `EffectsManager`.

For more detailed information about the system design, refer to `dmx-controller-design-spec.md` and `dmx-controller-design-spec-additional-info.md`.
