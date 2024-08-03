# DMX Light Controller Application Design Specification

## 1. System Overview

The DMX light controller application will manage 21 light fixtures, each with 8 channels, all within a single DMX universe. The system will support continuous morphing color changes across all fixtures while allowing for interruptions and transitions to specific fixtures.

## 2. Key Components

### 2.1 DMX State Manager

- Maintains the current state of all DMX channels (168 total: 21 fixtures * 8 channels)
- Provides thread-safe access to channel values
- Implements locking mechanism to prevent race conditions

### 2.2 Sequence Runner

- Executes the main lighting sequence (slow morphing color changes)
- Runs in a separate thread to allow for non-blocking operation

### 2.3 Interrupt Handler

- Manages interruptions for specific fixtures
- Coordinates the transition between main sequence and interrupted states

### 2.4 DMX Output Manager

- Handles the actual output of DMX data to the fixtures
- Implements DMX protocol specifics

## 3. Architecture and Workflow

### 3.1 Main Sequence Execution

1. The Sequence Runner continuously calculates and updates channel values for all fixtures.
2. It uses the DMX State Manager to update channel values atomically.
3. The DMX Output Manager reads from the DMX State Manager and sends data to the fixtures at regular intervals (typically 40 times per second for DMX).

### 3.2 Interruption Workflow

1. When an interruption is triggered:
   a. The Interrupt Handler acquires a lock on the specific fixtures to be interrupted.
   b. It resets the channels for these fixtures to 0 in the DMX State Manager.
   c. It executes the interruption sequence, updating the DMX State Manager as needed.
   d. Once complete, it resets the channels to 0 again.
   e. Finally, it releases the lock on the fixtures.

2. The main Sequence Runner continues to run unaffected for non-interrupted fixtures.

## 4. Detailed Component Specifications

### 4.1 DMX State Manager

```python
class DMXStateManager:
    def __init__(self, num_fixtures, channels_per_fixture):
        self.state = [0] * (num_fixtures * channels_per_fixture)
        self.locks = [threading.Lock() for _ in range(num_fixtures)]

    def update_fixture(self, fixture_id, channel_values):
        with self.locks[fixture_id]:
            start_index = fixture_id * 8
            self.state[start_index:start_index + 8] = channel_values

    def get_full_state(self):
        state = [int(value) if isinstance(value, (int, float)) else 0 for value in self.state]
        logger.debug(f"Full DMX state (first 10 values): {state[:10]}")
        logger.debug(f"State type: {type(state)}, Length: {len(state)}")
        return state

    def reset_fixture(self, fixture_id):
        with self.locks[fixture_id]:
            start_index = fixture_id * 8
            self.state[start_index:start_index + 8] = [0] * 8
```

### 4.2 Sequence Runner

```python
class SequenceRunner(threading.Thread):
    def __init__(self, dmx_state_manager):
        super().__init__()
        self.dmx_state_manager = dmx_state_manager
        self.running = True

    def run(self):
        while self.running:
            # Calculate new values for all fixtures
            for fixture_id in range(21):
                new_values = self.calculate_new_values(fixture_id)
                self.dmx_state_manager.update_fixture(fixture_id, new_values)
            time.sleep(0.025)  # 40Hz update rate

    def calculate_new_values(self, fixture_id):
        # Implement your color morphing logic here
        pass
```

### 4.3 Interrupt Handler

```python
class InterruptHandler:
    def __init__(self, dmx_state_manager):
        self.dmx_state_manager = dmx_state_manager

    def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        self.dmx_state_manager.reset_fixture(fixture_id)
        
        start_time = time.time()
        while time.time() - start_time < duration:
            new_values = interrupt_sequence(fixture_id, time.time() - start_time)
            self.dmx_state_manager.update_fixture(fixture_id, new_values)
            time.sleep(0.025)  # 40Hz update rate

        self.dmx_state_manager.reset_fixture(fixture_id)
```

### 4.4 DMX Output Manager

```python
class DMXOutputManager(threading.Thread):
    def __init__(self, dmx_state_manager, universe=0):
        super().__init__()
        self.dmx_state_manager = dmx_state_manager
        self.universe = universe
        self.running = True

    def run(self):
        while self.running:
            state = self.dmx_state_manager.get_full_state()
            self.send_dmx_data(state)
            time.sleep(0.025)  # 40Hz update rate

    def send_dmx_data(self, state):
        # Implement your DMX protocol sending logic here
        pass
```

## 5. Best Practices and Optimizations

1. Use efficient data structures (e.g., NumPy arrays) for fast numerical operations in color calculations.
2. Implement fine-grained locking to minimize contention and maximize parallelism.
3. Use a high-precision timer for accurate timing in color transitions and DMX output.
4. Implement a double-buffering system in the DMX Output Manager to ensure smooth transitions.
5. Use interpolation techniques for smooth color morphing between keyframes.
6. Implement a priority system for handling multiple simultaneous interrupts.
7. Use memory-mapped I/O for faster DMX output if supported by your hardware.

## 6. Future Considerations

1. Implement a plugin system for easily adding new sequences and effects.
2. Create a user interface for real-time control and monitoring.
3. Add support for multiple DMX universes to handle more complex setups.
4. Implement fixture profiles to support different types of lights with varying capabilities.

