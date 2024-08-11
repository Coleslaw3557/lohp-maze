# LoHP-MazeManager Control System

## Project Overview

The LoHP-MazeManager Control System is a sophisticated lighting and audio control system designed for interactive maze environments. It consists of a central server application and distributed client applications running on Raspberry Pi units throughout the maze.

### Key Features:

1. Centralized control of lighting effects and audio playback
2. Real-time synchronization of effects across multiple rooms
3. Theme-based ambient lighting with smooth transitions
4. Trigger-based effect activation
5. WebSocket-based communication between server and clients
6. DMX512 protocol support for lighting control
7. Customizable effects and themes

## System Architecture

### Server Application

The server application is the central control unit of the system. It manages the overall state of the maze, coordinates effects across rooms, and communicates with client units.

Key components:
- DMX State Manager: Manages the state of all DMX fixtures
- Effects Manager: Handles the creation and execution of lighting effects
- Theme Manager: Manages ambient lighting themes
- Remote Host Manager: Coordinates communication with client units
- WebSocket Handler: Manages real-time communication with clients

### Client Application

The client application runs on Raspberry Pi units distributed throughout the maze. It handles local audio playback, monitors triggers, and executes lighting commands received from the server.

Key components:
- WebSocket Client: Maintains connection with the server
- Audio Manager: Handles local audio playback and caching
- Trigger Manager: Monitors GPIO pins for trigger events

## Setup and Installation

### Server Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `light_config.json` with your DMX fixture layout
4. Run the server: `python main.py`

### Client Setup

1. Copy the `client/` folder to your Raspberry Pi
2. Install dependencies: `pip install -r client/requirements.txt`
3. Configure `client/config.json` with server IP and associated rooms
4. Run the client: `python client/main.py`

## Adding New Effects

To add a new effect:

1. Create a new Python file in the `effects/` directory (e.g., `new_effect.py`)
2. Define a function that returns a dictionary with the effect configuration:

```python
def create_new_effect():
    return {
        "duration": 5.0,
        "description": "Description of the new effect",
        "steps": [
            {"time": 0.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0}},
            {"time": 2.5, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0}},
            {"time": 5.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0}}
        ]
    }
```

3. Import the new effect in `effects/__init__.py`
4. Add the effect to the `initialize_effects()` method in `effects_manager.py`

## Adding New Themes

To add a new theme:

1. Open `theme_manager.py`
2. Add a new theme configuration to the `load_themes()` method:

```python
"NewTheme": {
    "duration": 300,
    "transition_speed": 0.05,
    "color_variation": 0.8,
    "intensity_fluctuation": 0.3,
    "overall_brightness": 0.7,
    "room_transition_speed": 0.02,
    "color_wheel_speed": 0.08
}
```

3. Adjust the parameters to create the desired ambient lighting effect

## API Endpoints

The server provides several API endpoints for control and monitoring:

- `GET /api/rooms`: Get all rooms in the maze
- `GET /api/effects`: Get all available effects
- `GET /api/themes`: Get all available themes
- `POST /api/set_theme`: Set the current theme
- `POST /api/run_effect`: Run an effect in a specific room
- `POST /api/set_master_brightness`: Set the master brightness for all lights

For full API documentation, refer to the `api-examples.md` file.

## Troubleshooting

- Check the server and client logs for error messages
- Ensure all Raspberry Pi units are connected to the same network as the server
- Verify that the correct IP addresses and port numbers are configured in `client/config.json`
- Check that all DMX fixtures are properly connected and addressed according to `light_config.json`

## Contributing

Contributions to the LoHP-MazeManager Control System are welcome! Please submit pull requests with any enhancements, bug fixes, or documentation improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
