# API Endpoints Examples

This document provides curl commands for all API endpoints. The server IP is 192.168.1.238.

## Get Rooms

Retrieves the list of rooms.

```bash
curl -X GET http://192.168.1.238:5000/api/rooms
```

## Get Effects Details

Retrieves the detailed list of available effects.

```bash
curl -X GET http://192.168.1.238:5000/api/effects_details
```

## Get Effects List

Retrieves a simplified list of effects.

```bash
curl -X GET http://192.168.1.238:5000/api/effects_list
```

## Get Themes

Retrieves the list of available themes.

```bash
curl -X GET http://192.168.1.238:5000/api/themes
```

## Get Light Models

Retrieves the list of light models.

```bash
curl -X GET http://192.168.1.238:5000/api/light_models
```

## Set Theme

Sets the current theme.

```bash
curl -X POST http://192.168.1.238:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "Ocean"}'
```

## Set Next Theme

Sets the next theme in the list.

```bash
curl -X POST http://192.168.1.238:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"next_theme": true}'
```

## Increment to Next Theme

Increments to the next theme in the list.

```bash
curl -X POST http://192.168.1.238:5000/api/set_next_theme
```

## Turn Off Theme

Turns off the current theme.

```bash
curl -X POST http://192.168.1.238:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "notheme"}'
```

## Run Effect

Runs an effect in a specific room.

```bash
curl -X POST http://192.168.1.238:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{
           "room": "Entrance",
           "effect_name": "Lightning",
           "audio": {
             "volume": 0.8,
             "loop": false
           }
         }'
```

## Set Master Brightness

Sets the master brightness for all lights.

```bash
curl -X POST http://192.168.1.238:5000/api/set_master_brightness \
     -H "Content-Type: application/json" \
     -d '{"brightness": 0.8}'
```

## Run Test

Runs a test for channels or effects.

```bash
curl -X POST http://192.168.1.238:5000/api/run_test \
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

## Stop Test

Stops the current test and resets all lights.

```bash
curl -X POST http://192.168.1.238:5000/api/stop_test
```

## Run Effect in All Rooms

Runs an effect in all rooms simultaneously.

```bash
curl -X POST http://192.168.1.238:5000/api/run_effect_all_rooms \
     -H "Content-Type: application/json" \
     -d '{"effect_name": "Lightning"}'
```

## Stop Effect

Stops the current effect in a specific room or all rooms.

```bash
curl -X POST http://192.168.1.238:5000/api/stop_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance"}'
```

To stop effects in all rooms, omit the "room" parameter:

```bash
curl -X POST http://192.168.1.238:5000/api/stop_effect \
     -H "Content-Type: application/json" \
     -d '{}'
```

## Start Background Music

Starts the background music on all connected clients.

```bash
curl -X POST http://192.168.1.238:5000/api/start_music
```

## Stop Background Music

Stops the background music on all connected clients.

```bash
curl -X POST http://192.168.1.238:5000/api/stop_music
```

These curl commands cover all the API endpoints available in the current implementation. You can use these for easy copy and pasting when interacting with the API.
