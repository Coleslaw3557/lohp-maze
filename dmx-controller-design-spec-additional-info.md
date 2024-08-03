# Escape Room DMX Light Controller System Design Specification

## 1. System Overview

The Escape Room DMX Light Controller is a Python-based application running on a Raspberry Pi (Headend-Pi) that manages DMX lighting for multiple rooms in an escape room experience. It supports dynamic effect triggering via HTTP requests, continuous theme playback, and expandability for various DMX light models and room configurations.

## 2. Key Components

### 2.1 DMX State Manager (from previous design)
- Maintains the current state of all DMX channels
- Provides thread-safe access to channel values
- Implements locking mechanism to prevent race conditions

### 2.2 FastAPI Web Server
- Handles incoming HTTP requests for triggering effects
- Provides endpoints for system status and configuration

### 2.3 Effect Manager
- Loads and manages effect definitions from JSON files
- Executes effects on specific rooms when triggered

### 2.4 Theme Manager
- Loads and manages theme plugins (Python functions)
- Continuously applies the current theme across all rooms

### 2.5 Room Manager
- Maintains the configuration of rooms and their associated lights
- Maps room names to DMX addresses

### 2.6 Light Model Manager
- Stores and retrieves configurations for different DMX light models

### 2.7 DMX Output Manager (from previous design, potentially modified)
- Handles the actual output of DMX data to the fixtures
- Implements DMX protocol specifics

## 3. Data Storage

### 3.1 Room Configuration (JSON)
```json
{
  "rooms": [
    {
      "name": "Entrance",
      "lights": [
        {
          "model": "ZQ01424",
          "dmx_address": 1
        }
      ]
    },
    {
      "name": "Cop Dodge",
      "lights": [
        {
          "model": "ZQ01424",
          "dmx_address": 9
        }
      ]
    },
    // ... other rooms ...
  ]
}
```

### 3.2 Light Model Configuration (JSON)
```json
{
  "ZQ01424": {
    "channels": [
      {"name": "red", "default": 0},
      {"name": "green", "default": 0},
      {"name": "blue", "default": 0},
      {"name": "white", "default": 0},
      {"name": "dimmer", "default": 255},
      {"name": "strobe", "default": 0},
      {"name": "mode", "default": 0},
      {"name": "motor", "default": 0}
    ]
  },
  "ZQ07010": {
    "channels": [
      // ... channel configuration for ZQ07010 ...
    ]
  }
}
```

### 3.3 Effect Configuration (JSON)
```json
{
  "cop_car_lights": {
    "room": "Cop Dodge",
    "duration": 10,
    "steps": [
      {
        "time": 0,
        "values": {"red": 255, "blue": 0}
      },
      {
        "time": 0.5,
        "values": {"red": 0, "blue": 255}
      },
      // ... more steps ...
    ]
  }
}
```

## 4. Component Specifications

### 4.1 FastAPI Web Server

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class EffectTrigger(BaseModel):
    room: str
    effect: str

@app.post("/trigger-effect")
async def trigger_effect(effect_trigger: EffectTrigger):
    # Trigger the effect in the specified room
    await effect_manager.trigger_effect(effect_trigger.room, effect_trigger.effect)
    return {"status": "success"}

@app.get("/status")
async def get_status():
    # Return current system status
    return {
        "current_theme": theme_manager.current_theme,
        "active_effects": effect_manager.active_effects
    }
```

### 4.2 Effect Manager

```python
import json
import asyncio

class EffectManager:
    def __init__(self, dmx_state_manager, room_manager):
        self.dmx_state_manager = dmx_state_manager
        self.room_manager = room_manager
        self.effects = self.load_effects()
        self.active_effects = {}

    def load_effects(self):
        with open('effects.json', 'r') as f:
            return json.load(f)

    async def trigger_effect(self, room, effect_name):
        if room not in self.room_manager.rooms or effect_name not in self.effects:
            raise ValueError("Invalid room or effect name")

        effect = self.effects[effect_name]
        self.active_effects[room] = effect_name
        
        for step in effect['steps']:
            await asyncio.sleep(step['time'])
            for light in self.room_manager.rooms[room]['lights']:
                self.dmx_state_manager.update_fixture(light['dmx_address'], step['values'])

        del self.active_effects[room]
```

### 4.3 Theme Manager

```python
import importlib
import asyncio

class ThemeManager:
    def __init__(self, dmx_state_manager, room_manager):
        self.dmx_state_manager = dmx_state_manager
        self.room_manager = room_manager
        self.current_theme = None
        self.themes = self.load_themes()

    def load_themes(self):
        # Load theme plugins dynamically
        return {
            'jungle': importlib.import_module('themes.jungle').apply_theme,
            # Add more themes as needed
        }

    async def run_theme(self, theme_name):
        self.current_theme = theme_name
        theme_func = self.themes[theme_name]
        while True:
            await theme_func(self.dmx_state_manager, self.room_manager)
            await asyncio.sleep(60)  # Loop every minute
```

### 4.4 Room Manager

```python
import json

class RoomManager:
    def __init__(self):
        self.rooms = self.load_room_config()

    def load_room_config(self):
        with open('room_config.json', 'r') as f:
            return json.load(f)['rooms']

    def get_room_lights(self, room_name):
        return self.rooms[room_name]['lights']
```

### 4.5 Light Model Manager

```python
import json

class LightModelManager:
    def __init__(self):
        self.models = self.load_model_config()

    def load_model_config(self):
        with open('light_models.json', 'r') as f:
            return json.load(f)

    def get_model_config(self, model_name):
        return self.models.get(model_name, {})
```

## 5. Main Application Loop

```python
import asyncio
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config

async def main():
    # Initialize components
    dmx_state_manager = DMXStateManager()
    room_manager = RoomManager()
    light_model_manager = LightModelManager()
    effect_manager = EffectManager(dmx_state_manager, room_manager)
    theme_manager = ThemeManager(dmx_state_manager, room_manager)
    dmx_output_manager = DMXOutputManager(dmx_state_manager)

    # Start DMX output manager
    asyncio.create_task(dmx_output_manager.run())

    # Start theme manager with default theme
    asyncio.create_task(theme_manager.run_theme('jungle'))

    # Initialize FastAPI app
    app = FastAPI()
    
    # Add routes to app...

    # Run FastAPI server
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    await serve(app, config)

if __name__ == "__main__":
    asyncio.run(main())
```

## 6. Expandability and Future Considerations

1. Plugin System: Implement a plugin architecture for easily adding new themes and effects.
2. Web UI: Develop a comprehensive web interface for managing rooms, effects, and themes.
3. Multi-universe Support: Extend the system to handle multiple DMX universes for larger setups.
4. Logging and Monitoring: Implement detailed logging and monitoring for troubleshooting and performance optimization.
5. Remote Management: Add secure remote management capabilities for off-site control and monitoring.

