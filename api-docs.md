# LoHP-MazeManager API Documentation

This document outlines the available API endpoints for the LoHP-MazeManager Control System.

## Base URL

All API requests should be made to:

```
http://<server-ip>:5000/api
```

Replace `<server-ip>` with the IP address or hostname of your LoHP-MazeManager server.

## Endpoints

### 1. Set Theme

Sets the current lighting theme for all rooms.

- **URL:** `/set_theme`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "theme_name": "[string]"
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "NeonNightlife"}'
```

### 2. Run Effect

Runs a specific effect in a given room.

- **URL:** `/run_effect`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "room": "[string]",
    "effect_name": "[string]"
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Lightning"}'
```

### 3. Set Master Brightness

Adjusts the master brightness for all lights.

- **URL:** `/set_master_brightness`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "brightness": [float]
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/set_master_brightness \
     -H "Content-Type: application/json" \
     -d '{"brightness": 0.8}'
```

### 4. Get Rooms

Retrieves the list of configured rooms.

- **URL:** `/rooms`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/rooms
```

### 5. Get Effects List

Retrieves the list of available effects.

- **URL:** `/effects_list`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/effects_list
```

### 6. Get Themes

Retrieves the list of available themes.

- **URL:** `/themes`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/themes
```

### 7. Start Background Music

Starts playing background music on all connected clients.

- **URL:** `/start_music`
- **Method:** `POST`

#### Example
```bash
curl -X POST http://localhost:5000/api/start_music
```

### 8. Stop Background Music

Stops the currently playing background music on all connected clients.

- **URL:** `/stop_music`
- **Method:** `POST`

#### Example
```bash
curl -X POST http://localhost:5000/api/stop_music
```

### 9. Run Test

Runs a test sequence for lighting or effects.

- **URL:** `/run_test`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "testType": "[string]",
    "rooms": ["[string]"],
    "channelValues": {
      "[channel]": [int]
    }
  }
  ```
  or
  ```json
  {
    "testType": "[string]",
    "rooms": ["[string]"],
    "effectName": "[string]"
  }
  ```

#### Example (Channel Test)
```bash
curl -X POST http://localhost:5000/api/run_test \
     -H "Content-Type: application/json" \
     -d '{
       "testType": "channel",
       "rooms": ["Entrance"],
       "channelValues": {
         "total_dimming": 255,
         "r_dimming": 255,
         "g_dimming": 0,
         "b_dimming": 0
       }
     }'
```

#### Example (Effect Test)
```bash
curl -X POST http://localhost:5000/api/run_test \
     -H "Content-Type: application/json" \
     -d '{
       "testType": "effect",
       "rooms": ["Entrance"],
       "effectName": "Lightning"
     }'
```

### 10. Stop Test

Stops any ongoing test and resets the lights.

- **URL:** `/stop_test`
- **Method:** `POST`

#### Example
```bash
curl -X POST http://localhost:5000/api/stop_test
```

### 11. Run Effect in All Rooms

Runs a specific effect in all rooms simultaneously.

- **URL:** `/run_effect_all_rooms`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "effect_name": "[string]",
    "audio": {
      "volume": [float],
      "loop": [boolean]
    }
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/run_effect_all_rooms \
     -H "Content-Type: application/json" \
     -d '{
       "effect_name": "Lightning",
       "audio": {
         "volume": 0.8,
         "loop": false
       }
     }'
```

## Error Handling

All API endpoints will return appropriate HTTP status codes:

- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error

Error responses will include a JSON body with an error message:

```json
{
  "status": "error",
  "message": "Error description"
}
```

## WebSocket API

In addition to the RESTful API, the system also supports real-time communication via WebSockets. The WebSocket server is available at:

```
ws://<server-ip>:8765
```

WebSocket messages are used for real-time updates and notifications between the server and connected clients. Refer to the WebSocket handler documentation for more details on the message formats and events.
