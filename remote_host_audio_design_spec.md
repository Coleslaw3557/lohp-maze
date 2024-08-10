# Remote Host and Audio Streaming Design Specification

## 1. Overview

This design specification outlines the server-side changes required to extend the LoHP-MazeManager Control System to support managing remote host clients and integrating audio streaming functionality. The enhancements will allow the system to:

1. Manage a list of remote host clients (Raspberry Pis) connected to switches in various rooms.
2. Handle POST requests from remote units to execute effects and themes.
3. Stream audio files over WebSocket connections to remote units based on triggered effects.

## 2. New Components

### 2.1 RemoteHostManager

Purpose: Manage the configuration and state of remote host clients.

Responsibilities:
- Load and maintain remote host configurations.
- Manage WebSocket connections to remote hosts.
- Route audio streams to appropriate remote hosts based on room associations.

### 2.2 AudioManager

Purpose: Handle audio file management, associations, and streaming.

Responsibilities:
- Manage audio file storage and retrieval.
- Maintain associations between effects and audio files.
- Prepare audio streams for WebSocket transmission.
- Coordinate audio playback with lighting effects.

### 2.3 WebSocketHandler

Purpose: Manage WebSocket connections and communication with remote hosts.

Responsibilities:
- Establish and maintain WebSocket connections with remote hosts.
- Handle incoming WebSocket messages from remote hosts.
- Send audio stream data and control messages to remote hosts.

## 3. Modifications to Existing Components

### 3.1 EffectsManager

Modifications:
- Extend effect definitions to include audio file information.
- Coordinate with AudioManager to sync audio with lighting effects.

### 3.2 LightConfigManager

Modifications:
- Extend room configuration to include speaker information and associated remote hosts.

### 3.3 Main Application (main.py)

Modifications:
- Initialize and integrate new RemoteHostManager, AudioManager, and WebSocketHandler components.
- Extend API endpoints to handle remote host interactions and audio-related requests.

## 4. New Configuration Files

### 4.1 remote_host_config.json

Purpose: Store configuration data for remote hosts.

Structure:
```json
{
  "remote_hosts": {
    "192.168.1.101": {
      "name": "Host1",
      "rooms": ["Cop Dodge", "Entrance"]
    },
    "192.168.1.102": {
      "name": "Host2",
      "rooms": ["Gate", "Guy Line Climb"]
    }
  }
}
```

### 4.2 audio_config.json

Purpose: Store audio file mappings for effects.

Structure:
```json
{
  "effects": {
    "Lightning": {
      "audio_file": "lightning_crack.mp3",
      "loop": false,
      "volume": 0.8
    },
    "Background Music": {
      "audio_file": "ambient_music.mp3",
      "loop": true,
      "volume": 0.5
    }
  },
  "default_volume": 0.7
}
```

## 5. API Extensions

### 5.1 POST /api/run_effect

Modifications:
- Accept additional parameters for audio control (e.g., volume, loop).
- Trigger audio streaming to relevant remote hosts.

Example request body:
```json
{
  "room": "Entrance",
  "effect_name": "Lightning",
  "audio": {
    "volume": 0.8,
    "loop": false
  }
}
```

### 5.2 GET /api/remote_hosts

New endpoint to retrieve information about connected remote hosts.

Example response:
```json
{
  "remote_hosts": [
    {
      "ip": "192.168.1.101",
      "name": "Host1",
      "rooms": ["Cop Dodge", "Entrance"],
      "status": "connected"
    },
    {
      "ip": "192.168.1.102",
      "name": "Host2",
      "rooms": ["Gate", "Guy Line Climb"],
      "status": "disconnected"
    }
  ]
}
```

## 6. WebSocket Protocol

### 6.1 Server to Remote Host Messages

- `audio_start`: Instruct the remote host to start playing an audio stream.
- `audio_stop`: Instruct the remote host to stop playing the current audio.
- `audio_data`: Send chunks of audio data to the remote host.

Example:
```json
{
  "type": "audio_start",
  "data": {
    "effect": "Lightning",
    "file": "lightning_crack.mp3",
    "volume": 0.8
  }
}
```

### 6.2 Remote Host to Server Messages

- `audio_status`: Report the current audio playback status.
- `connection_status`: Report the remote host's connection status.

Example:
```json
{
  "type": "audio_status",
  "data": {
    "status": "playing",
    "effect": "Lightning",
    "timestamp": 1234567890
  }
}
```

## 7. New Audio Module

### 7.1 audio_module.py

This new module will encapsulate all audio-related functionality:

- AudioManager class
- Audio file handling and management
- Effect-to-audio associations
- Audio streaming preparation

### 7.2 Integration with Existing Components

- EffectsManager will use AudioManager to retrieve audio information for effects.
- RemoteHostManager will use AudioManager to prepare audio streams for transmission.
- WebSocketHandler will use AudioManager to send audio data to remote hosts.

## 8. Implementation Steps

1. Create new Python files for RemoteHostManager, WebSocketHandler, and the new audio_module.py.
2. Implement AudioManager class in audio_module.py with effect-to-audio association functionality.
3. Modify EffectsManager to use AudioManager for retrieving audio information.
4. Update LightConfigManager to include speaker and remote host associations in room configurations.
5. Extend main.py to initialize and integrate new components, including the audio module.
6. Implement new API endpoints and modify existing ones as specified.
7. Develop WebSocket communication protocol and implement in WebSocketHandler.
8. Create new configuration files: remote_host_config.json and audio_config.json.
9. Update existing configuration files to include audio-related information.
10. Implement error handling and logging for new components and functionalities.
11. Develop unit tests for new components and modified functionalities, including audio module tests.

## 8. Considerations

- Ensure proper error handling for network issues and disconnections.
- Implement reconnection logic for remote hosts.
- Consider using a message queue system for reliable audio data transmission.
- Implement proper synchronization mechanisms to ensure audio and lighting effects remain in sync.
- Consider security measures such as authentication and encryption for WebSocket connections.
- Optimize audio streaming for low latency and efficient bandwidth usage.
- Implement a fallback mechanism for audio playback in case of streaming issues.

By following this design specification, we can extend the LoHP-MazeManager Control System to support remote hosts and audio streaming, creating a more immersive and synchronized audio-visual experience for the escape room setup.
