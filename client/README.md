# LoHP-MazeManager Remote Unit Client

This is the client application for the LoHP-MazeManager Control System, designed to run on Raspberry Pi units distributed throughout the maze.

## Setup

1. Ensure you have Python 3.7+ installed on your Raspberry Pi.

2. Clone this repository or copy the client folder to your Raspberry Pi.

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure the `config.json` file with your specific settings:
   - Set the correct `server_ip` and `server_port`
   - Update the `unit_name` and `associated_room`
   - Configure any GPIO triggers as needed

5. Ensure the `cache_dir` specified in `config.json` exists and is writable.

## Usage

To start the client application, run:

```
python main.py
```

The client will automatically:
- Connect to the central server
- Listen for audio commands
- Monitor configured triggers
- Manage local audio playback

## Features

- WebSocket communication with the central server
- Local audio playback and caching
- GPIO trigger monitoring
- Time synchronization with the server

## Troubleshooting

- If the client fails to connect to the server, check your network settings and the server IP/port in `config.json`.
- For audio issues, ensure the correct audio output device is set in `config.json` and that the necessary audio files are available.
- If triggers are not working, verify the GPIO pin configurations in `config.json` and check your physical connections.

## Logs

Logs are output to the console by default. You can redirect them to a file if needed:

```
python main.py > client.log 2>&1
```

## Docker

To run the client using Docker:

1. Build the Docker image:
   ```
   docker build -t lohp-client .
   ```

2. Run the container:
   ```
   docker run --device /dev/snd:/dev/snd --privileged -v /path/to/your/config.json:/app/config.json -v /path/to/your/cache:/app/cache lohp-client
   ```

Replace `/path/to/your/config.json` and `/path/to/your/cache` with the actual paths on your Raspberry Pi.

## Support

For any issues or questions, please contact the LoHP-MazeManager development team.
