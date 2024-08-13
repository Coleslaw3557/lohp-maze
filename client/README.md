# Remote Unit Client

## Overview

This is the client-side application for the Remote Unit system, designed to run on Raspberry Pi devices. It manages audio playback, handles triggers, and communicates with a central server via WebSocket.

## Features

- WebSocket communication with the central server
- Audio playback management using VLC
- GPIO trigger handling
- Time synchronization with the server
- Background music support
- Effect preparation and execution
- Dockerized deployment

## Components

### 1. WebSocketClient (websocket_client.py)

The core component that handles communication with the server. It:
- Establishes and maintains a WebSocket connection
- Handles various message types from the server
- Manages reconnection attempts on connection loss

### 2. AudioManager (audio_manager.py)

Responsible for audio playback. It:
- Initializes the VLC instance for audio playback
- Manages audio file caching and downloads
- Handles playback of effect audio and background music

### 3. TriggerManager (trigger_manager.py)

Manages GPIO triggers on the Raspberry Pi. It:
- Sets up GPIO pins based on the configuration
- Monitors triggers and reports events to the server

### 4. ConfigManager (config_manager.py)

Handles the loading and management of the client configuration. It:
- Loads the configuration from a JSON file
- Provides access to configuration parameters

### 5. SyncManager (sync_manager.py)

Manages time synchronization with the server. It:
- Keeps track of the time offset between client and server
- Provides methods to get the synced time

### 6. Main Application (main.py)

The entry point of the application. It:
- Initializes all components
- Starts the WebSocket connection and listening loop
- Manages the overall flow of the application

## Configuration

The client is configured using a `config.json` file, which includes:
- Server IP and port
- Unit name and associated rooms
- Audio output device
- GPIO trigger configurations
- Cache directory location

## Deployment

The application is containerized using Docker for easy deployment and management. The `Dockerfile` and `docker-compose.yml` files are provided for building and running the container.

### Running the Client

1. Ensure Docker and Docker Compose are installed on your Raspberry Pi.
2. Navigate to the client directory.
3. Build and start the container:
   ```
   docker-compose up --build
   ```

## Development and Debugging

- Logging is set up to provide detailed information about the client's operations.
- The code is structured to allow easy extension and modification of functionality.
- Error handling and reconnection logic are implemented to ensure robustness.

## Future Improvements

- Implement more sophisticated error handling and recovery mechanisms.
- Add support for more types of triggers and effects.
- Enhance the audio management system to support more complex audio scenarios.
- Implement a local web interface for status monitoring and basic control.

## Security Considerations

- Ensure that the WebSocket connection is secured (e.g., using WSS instead of WS).
- Implement authentication mechanisms for the client-server communication.
- Regularly update dependencies to address potential vulnerabilities.

## Contributing

Contributions to improve the client are welcome. Please ensure to follow the existing code style and add appropriate tests for new features.
