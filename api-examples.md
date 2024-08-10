# API Examples for LoHP-MazeManager Control System

This document provides examples of how to use the API endpoints for the LoHP-MazeManager Control System.

## Get Rooms

Retrieve a list of all rooms and their configurations.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/rooms
```

## Get Effects

There are two endpoints for retrieving effects:

### Get Detailed Effects Information

Retrieve detailed information about all available effects.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/effects_details
```

### Get Effects List

Retrieve a simple list of all available effects and their descriptions.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/effects_list
```

## Get Themes

Retrieve a list of all available themes.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/themes
```

## Set Theme

Set the current theme for the entire maze.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "Ocean"}'
```

## Run Effect in a Specific Room

Trigger an effect in a specific room.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Lightning"}'
```

Available effects:
- Lightning: Simulates a lightning strike with bright flashes
- PoliceLights: Alternating red and blue flashes simulating police lights
- GateInspection: Bright white light for gate inspection, lasting 5 seconds
- GateGreeters: Welcoming effect with gentle color transitions and pulsing
- WrongAnswer: Three quick red flashes to indicate a wrong answer
- CorrectAnswer: Three quick green flashes to indicate a correct answer
- Entrance: Welcoming effect with warm colors and gentle pulsing for the entrance
- GuyLineClimb: Simulates climbing vines in a jungle with blues and greens and a low strobe
- SparkPony: Sparkling effect simulating a 'sparkle pony' with rapid color changes
- PortoStandBy: Gentle pulsing blue light for Porto Room standby state
- PortoHit: Simulates a hit on the porto-potty with a quick flash and fade
- CuddlePuddle: Soft, warm, and inviting light effect for the Cuddle Puddle area
- PhotoBomb-BG: Background effect for the Photo Bomb room with subtle color changes
- PhotoBomb-Spot: Spotlight effect for the Photo Bomb room with a quick flash and fade
- DeepPlaya-BG: Background effect for the Deep Playa area with subtle, slow-changing colors

## Set Master Brightness

Adjust the master brightness for all lights.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/set_master_brightness \
     -H "Content-Type: application/json" \
     -d '{"brightness": 0.8}'
```

## Run Effect in All Rooms

Trigger an effect in all rooms simultaneously.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_effect_all_rooms \
     -H "Content-Type: application/json" \
     -d '{"effect_name": "Lightning"}'
```

## Get Light Models

Retrieve a list of all light fixture models and their characteristics.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/light_models
```

## Run Test

Run a channel or effect test in specific rooms.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_test \
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

Or for an effect test:

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_test \
     -H "Content-Type: application/json" \
     -d '{
       "testType": "effect",
       "rooms": ["Entrance"],
       "effectName": "Lightning"
     }'
```

## Stop Test

Stop the current test and reset all lights.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/stop_test
```

These examples cover the main API endpoints available in the current version of the LoHP-MazeManager Control System. Remember to replace `$CONTROLLER_IP` with the actual IP address of your controller.
