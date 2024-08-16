# LoHP-MazeManager Remote Unit Client

## Overview

This is the client-side application for the LoHP-MazeManager system, designed to run on Raspberry Pi devices. It manages audio playback, handles various types of triggers (GPIO, ADC), controls laser modules, and communicates with a central server via WebSocket.

## Features

- WebSocket communication with the central server
- Audio playback management using PyAudio
- Support for multiple trigger types (GPIO, ADC)
- Laser module control
- Time synchronization with the server
- Background music support
- Effect preparation and execution
- Dockerized deployment
- Support for multiple unit configurations (A, B, C)

## Components

### 1. WebSocketClient (websocket_client.py)

Handles communication with the server:
- Establishes and maintains a WebSocket connection
- Processes various message types from the server
- Manages reconnection attempts on connection loss

### 2. AudioManager (audio_manager.py)

Manages audio playback:
- Initializes PyAudio for audio playback
- Handles audio file caching and downloads
- Manages playback of effect audio and background music

### 3. TriggerManager (trigger_manager.py)

Manages various types of triggers:
- Sets up GPIO pins for laser modules and buttons
- Configures ADC channels for analog inputs (e.g., resistor ladders, piezo sensors)
- Monitors triggers and reports events to the server

### 4. ConfigManager (config_manager.py)

Handles client configuration:
- Loads the configuration from a JSON file (config-unit-a.json, config-unit-b.json, or config-unit-c.json)
- Provides access to configuration parameters

### 5. SyncManager (sync_manager.py)

Manages time synchronization:
- Keeps track of the time offset between client and server
- Provides methods to get the synced time

### 6. Main Application (main.py)

The entry point of the application:
- Initializes all components based on the unit configuration
- Starts the WebSocket connection and listening loop
- Manages the overall flow of the application

## Configuration

The client uses unit-specific configuration files:
- `config-unit-a.json`: Configuration for Unit A
- `config-unit-b.json`: Configuration for Unit B
- `config-unit-c.json`: Configuration for Unit C

These files include:
- Server IP and port
- Unit name and associated rooms
- Audio output device
- Trigger configurations (GPIO, ADC)
- Laser module configurations
- Cache directory location

## Deployment

The application is containerized using Docker for easy deployment and management.

### Running the Client

1. Ensure Docker and Docker Compose are installed on your Raspberry Pi.
2. Navigate to the client directory.
3. Set the `UNIT_CONFIG` environment variable to specify which unit configuration to use:
   ```
   export UNIT_CONFIG=config-unit-b.json
   ```
4. Build and start the container:
   ```
   docker-compose up --build
   ```

## Development and Debugging

- Logging is set up to provide detailed information about the client's operations.
- The code is structured to allow easy extension and modification of functionality.
- Error handling and reconnection logic are implemented to ensure robustness.
- Unit tests are available in the `tests` directory for verifying component functionality.

## Security Considerations

- The WebSocket connection should be secured (e.g., using WSS instead of WS) in production.
- Implement authentication mechanisms for the client-server communication.
- Regularly update dependencies to address potential vulnerabilities.
- Ensure proper access controls on the Raspberry Pi devices.

## Contributing

Contributions to improve the client are welcome. Please ensure to follow the existing code style and add appropriate tests for new features. When adding new functionality, consider compatibility with all unit configurations (A, B, C).
