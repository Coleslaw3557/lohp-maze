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

### 5. Interrupt Handler (`interrupt_handler.py`)

Manages interruptions for specific fixtures:
- Coordinates transitions between main sequence and interrupted states
- Allows for precise control of individual fixtures during effects

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
- Effects: Create and trigger lighting effects
- Themes: Set and control overarching lighting themes
- Test Mode: Real-time testing of individual fixtures and effects

### API Examples

List all rooms:
```bash
curl -X GET http://localhost:5000/api/rooms
```

List all effects:
```bash
curl -X GET http://localhost:5000/api/effects
```

List all themes:
```bash
curl -X GET http://localhost:5000/api/themes
```

Set a theme:
```bash
curl -X POST http://localhost:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "Jungle"}'
```

Run an effect in a specific room:
```bash
curl -X POST http://localhost:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Lightning"}'
```

Set master brightness:
```bash
curl -X POST http://localhost:5000/api/set_master_brightness \
     -H "Content-Type: application/json" \
     -d '{"brightness": 0.8}'
```

Trigger lightning effect:
```bash
curl -X POST http://localhost:5000/api/trigger_lightning
```

## Technical Considerations

- The system uses a fixed 44Hz update rate for DMX communication to ensure smooth transitions and effects.
- Thread-safe operations are implemented throughout to handle concurrent access to the DMX interface and state management.
- The Effects Manager uses a sophisticated algorithm to generate dynamic themes based on parameters like color variation, intensity fluctuation, and overall brightness.
- The Interrupt Handler allows for precise control of individual fixtures without disrupting the overall lighting sequence.
- Error handling and logging are implemented at multiple levels for robust operation and debugging.
- Master brightness control affects all lighting outputs, allowing for global intensity adjustment without altering individual effect or theme designs.
