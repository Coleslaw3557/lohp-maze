# Adding New Effects to the LoHP-MazeManager Control System

This guide explains how to add new effects to the LoHP-MazeManager Control System.

## Steps to Add a New Effect

1. Define the effect in `effects_manager.py`:
   - Create a new method in the `EffectsManager` class, e.g., `create_new_effect()`.
   - Define the effect's parameters, including duration, description, and steps.
   - Use `self.add_effect()` to add the new effect to the system.

2. Initialize the effect in `effects_manager.py`:
   - Add a call to your new effect creation method in the `__init__` method of `EffectsManager`.

3. Update `main.py`:
   - Add a call to create your new effect in the `if __name__ == '__main__':` block.

4. (Optional) Update `api-examples.md`:
   - If your effect can be triggered via API, add an example of how to call it.

## Example

Here's an example of how to add a new "Strobe" effect:

1. In `effects_manager.py`, add:

```python
def create_strobe_effect(self):
    strobe_effect = {
        "duration": 5.0,
        "description": "Rapid flashing white light",
        "steps": []
    }
    for i in range(50):  # 50 flashes over 5 seconds
        t = i * 0.1
        strobe_effect["steps"].extend([
            {"time": t, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255}},
            {"time": t + 0.05, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0}}
        ])
    self.add_effect("Strobe", strobe_effect)
    logger.info(f"Strobe effect created with {len(strobe_effect['steps'])} steps over {strobe_effect['duration']} seconds")
```

2. In the `__init__` method of `EffectsManager`, add:

```python
self.create_strobe_effect()
```

3. In `main.py`, add to the `if __name__ == '__main__':` block:

```python
effects_manager.create_strobe_effect()
```

4. In `api-examples.md`, add:

```markdown
## Trigger Strobe Effect

```bash
curl -X POST http://$CONTROLLER_IP:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Strobe"}'
```
```

After following these steps, the new "Strobe" effect will be available in the system and can be triggered like any other effect.

Remember to test your new effect thoroughly to ensure it works as expected and doesn't interfere with other system functionalities.
