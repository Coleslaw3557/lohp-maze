
    Create the systemd service file:

sudo nano /etc/systemd/system/lohp-client.service

    Add this content to the file:

[Unit]
Description=LOHP Client Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/dietpi/lohp-client
Environment=UNIT_CONFIG=config-unit-a.json
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

# Set UNIT_CONFIG to this unit's config file (config-unit-a/b/c.json,
# or config-single-pi.json for the consolidated multi-zone unit).

[Install]
WantedBy=multi-user.target

    Save and exit the editor.

    Reload systemd:

sudo systemctl daemon-reload

    Enable the service:

sudo systemctl enable lohp-client.service

    Start the service:

sudo systemctl start lohp-client.service

    Check status:

sudo systemctl status lohp-client.service

    Reboot to test:

sudo reboot

