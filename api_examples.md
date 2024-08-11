# API Endpoints Examples

This document provides examples for all API endpoints. The server IP is 192.168.1.238.

## Get Rooms

Retrieves the list of rooms.

```
GET http://192.168.1.238:5000/api/rooms
```

Example response:
```json
{
  "Entrance": [{"model": "Par Light - Model ZQ01424", "start_address": 1}],
  "Cop Dodge": [{"model": "Par Light - Model ZQ01424", "start_address": 9}],
  "Gate": [{"model": "Par Light - Model ZQ01424", "start_address": 17}]
}
```

## Get Effects

Retrieves the list of available effects.

```
GET http://192.168.1.238:5000/api/effects_details
```

Example response:
```json
{
  "Lightning": {
    "duration": 3.5,
    "description": "Simulates a lightning strike with bright flashes, matching the audio spectrogram"
  },
  "PoliceLights": {
    "duration": 15.0,
    "description": "Alternating red and blue flashes simulating police lights"
  }
}
```

## Get Effects List

Retrieves a simplified list of effects.

```
GET http://192.168.1.238:5000/api/effects_list
```

Example response:
```json
{
  "Lightning": "Simulates a lightning strike with bright flashes, matching the audio spectrogram",
  "PoliceLights": "Alternating red and blue flashes simulating police lights"
}
```

## Get Themes

Retrieves the list of available themes.

```
GET http://192.168.1.238:5000/api/themes
```

Example response:
```json
{
  "Ocean": {
    "duration": 300,
    "transition_speed": 0.05,
    "color_variation": 0.8,
    "intensity_fluctuation": 0.3,
    "overall_brightness": 0.7,
    "blue_green_balance": 0.9,
    "room_transition_speed": 0.02,
    "color_wheel_speed": 0.08
  },
  "Jungle": {
    "duration": 300,
    "transition_speed": 0.05,
    "color_variation": 0.9,
    "intensity_fluctuation": 0.4,
    "overall_brightness": 0.6,
    "green_blue_balance": 0.3,
    "room_transition_speed": 0.02,
    "color_wheel_speed": 0.09
  }
}
```

## Get Light Models

Retrieves the list of light models.

```
GET http://192.168.1.238:5000/api/light_models
```

Example response:
```json
{
  "Par Light - Model ZQ01424": {
    "channels": {
      "total_dimming": 0,
      "r_dimming": 1,
      "g_dimming": 2,
      "b_dimming": 3,
      "w_dimming": 4,
      "total_strobe": 5,
      "function_selection": 6,
      "function_speed": 7
    },
    "type": "RGBW"
  },
  "U'King LED Par Light - Model ZQ07010/ZQ07011": {
    "channels": {
      "master_dimmer": 0,
      "red": 1,
      "green": 2,
      "blue": 3,
      "white": 4,
      "color_macro": 5
    }
  }
}
```

## Set Theme

Sets the current theme.

```
POST http://192.168.1.238:5000/api/set_theme
Content-Type: application/json

{
  "theme_name": "Ocean"
}
```

Example response:
```json
{
  "status": "success",
  "message": "Theme set to Ocean"
}
```

## Run Effect

Runs an effect in a specific room.

```
POST http://192.168.1.238:5000/api/run_effect
Content-Type: application/json

{
  "room": "Entrance",
  "effect_name": "Lightning",
  "audio": {
    "volume": 0.8,
    "loop": false
  }
}
```

Example response:
```json
{
  "status": "success",
  "message": "Effect Lightning executed in room Entrance"
}
```

## Set Master Brightness

Sets the master brightness for all lights.

```
POST http://192.168.1.238:5000/api/set_master_brightness
Content-Type: application/json

{
  "brightness": 0.8
}
```

Example response:
```json
{
  "status": "success",
  "master_brightness": 0.8
}
```

## Run Test

Runs a test for channels or effects.

```
POST http://192.168.1.238:5000/api/run_test
Content-Type: application/json

{
  "testType": "channel",
  "rooms": ["Entrance"],
  "channelValues": {
    "total_dimming": 255,
    "r_dimming": 255,
    "g_dimming": 0,
    "b_dimming": 0
  }
}
```

Example response:
```json
{
  "message": "Channel test applied to rooms: Entrance"
}
```

## Stop Test

Stops the current test and resets all lights.

```
POST http://192.168.1.238:5000/api/stop_test
```

Example response:
```json
{
  "message": "Test stopped and lights reset"
}
```

## Run Effect in All Rooms

Runs an effect in all rooms simultaneously.

```
POST http://192.168.1.238:5000/api/run_effect_all_rooms
Content-Type: application/json

{
  "effect_name": "Lightning"
}
```

Example response:
```json
{
  "status": "success",
  "message": "Effect Lightning executed in all rooms simultaneously"
}
```

These examples cover all the API endpoints available in the current implementation. You can use these as a reference when interacting with the API.
