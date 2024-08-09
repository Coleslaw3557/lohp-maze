# API Examples for LoHP-MazeManager Control System

This document provides examples of how to use the API endpoints for the LoHP-MazeManager Control System.

## Get Rooms

Retrieve a list of all rooms and their configurations.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/rooms
```

## Get Effects

Retrieve a list of all available effects.

```bash
curl -X GET http://$CONTROLLER_IP:5000/api/effects
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
     -d '{"theme_name": "Jungle"}'
```

## Run Effect in a Specific Room

Trigger an effect in a specific room (asynchronous).

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Lightning"}'
```

## Run Effect Synchronously in a Specific Room

Trigger an effect in a specific room and wait for it to complete (synchronous).

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_effect_sync \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Lightning"}'
```

## Set Master Brightness

Adjust the master brightness for all lights.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/set_master_brightness \
     -H "Content-Type: application/json" \
     -d '{"brightness": 0.8}'
```

## Trigger Lightning Effect

Trigger the lightning effect across all rooms.

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/trigger_lightning
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

These examples cover the main API endpoints available in the current version of the LoHP-MazeManager Control System. Remember to replace `$CONTROLLER_IP` with the actual IP address of your controller.
