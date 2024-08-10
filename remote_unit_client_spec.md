# Remote Unit Client Specification for LoHP-MazeManager Control System

## 1. Overview

The Remote Unit Client is a Python-based application designed to run on Raspberry Pi units distributed throughout the maze. It will communicate with the central LoHP-MazeManager Control System server, handle audio playback, and manage local triggers (e.g., buttons, sensors).

## 2. Key Components

### 2.1 WebSocket Client
- Establishes and maintains a WebSocket connection with the central server.
- Handles incoming messages for audio control.
- Sends status updates, trigger events, and acknowledgments back to the server.

### 2.2 Audio Manager
- Manages local audio playback using a library like PyAudio or pygame.
- Handles audio file caching for improved performance.
- Controls volume and looping of audio tracks.

### 2.3 Trigger Manager
- Monitors and manages local triggers (e.g., buttons, sensors) connected to the Raspberry Pi.
- Sends trigger events to the server when activated.

### 2.4 Configuration Manager
- Loads and manages the local configuration file.
- Stores settings such as server IP, associated room, and device-specific parameters.

### 2.5 Synchronization Manager
- Implements time synchronization with the server using a protocol like PTP.
- Ensures accurate timing for audio playback and trigger events.

## 3. Configuration File (config.json)

```json
{
  "server_ip": "192.168.1.100",
  "server_port": 5000,
  "unit_name": "RPi-Unit-1",
  "associated_room": "Entrance",
  "audio_output_device": "default",
  "triggers": [
    {
      "name": "Button1",
      "type": "gpio",
      "pin": 17
    },
    {
      "name": "Sensor1",
      "type": "gpio",
      "pin": 18
    }
  ],
  "cache_dir": "/home/pi/lohp_cache"
}
```

## 4. Key Functionalities

### 4.1 WebSocket Communication
- Connect to server using WebSocket protocol.
- Handle incoming messages:
  - `audio_start`: Begin audio playback.
  - `audio_stop`: Stop current audio playback.
  - `effect_trigger`: Trigger a local effect (if applicable).
  - `sync_time`: Synchronize local clock with server.
- Send outgoing messages:
  - `status_update`: Regularly inform server of client status.
  - `effect_complete`: Notify when an effect has finished.

### 4.2 Audio Playback
- Support various audio formats (mp3, wav, ogg).
- Implement audio caching for frequently used sounds.
- Allow volume control and looping as specified by server commands.

### 4.3 Effect Handling
- If `has_local_lighting` is true, interpret and execute lighting effect commands.
- Use a standardized effect format compatible with the server's effect definitions.

### 4.4 Synchronization
- Implement PTP (Precision Time Protocol) for accurate time synchronization.
- Use synchronized time for precise audio and effect timing.

### 4.5 Error Handling and Recovery
- Implement automatic reconnection to server on connection loss.
- Cache recent commands to handle brief network interruptions.
- Provide fallback behaviors for common failure scenarios.

## 5. Performance Considerations

- Use efficient audio libraries for low-latency playback.
- Implement a threaded or asynchronous architecture for responsive handling of multiple tasks.
- Optimize network communication to minimize latency.
- Use memory-mapped files for quick access to cached audio and effect data.

## 6. Security Considerations

- Implement secure WebSocket connections (WSS) with proper certificate validation.
- Use authentication tokens for connecting to the server.
- Sanitize and validate all incoming data from the server.

## 7. Logging and Monitoring

- Implement comprehensive logging for troubleshooting.
- Include options for different log levels (DEBUG, INFO, WARNING, ERROR).
- Periodically send health status to the central server.

## 8. Future Expansion

- Design the system to be modular, allowing easy addition of new features.
- Consider a plugin architecture for custom effects or device-specific functionalities.
- Plan for potential integration with other sensors or interactive elements in the maze.

## 9. Development and Deployment

- Use Python 3.7+ for development.
- Create a requirements.txt file for easy dependency management.
- Develop a simple installation script for setting up new Raspberry Pi units.
- Include unit tests for critical components.
- Document the API and provide example usage for future developers.

By following this specification, the Remote Unit Client will be able to efficiently communicate with the LoHP-MazeManager Control System server, handle audio playback, and manage local effects, creating a cohesive and immersive experience across the entire maze installation.
