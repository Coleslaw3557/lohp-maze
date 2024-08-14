Here are the directions for auto-starting lohp-server Docker Compose on DietPi:

    Create the systemd service file:

sudo nano /etc/systemd/system/lohp-server.service

    Add this content to the file:

[Unit]
Description=LOHP Server Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/dietpi/lohp-server
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target

    Save and exit the editor.

    Reload systemd:

sudo systemctl daemon-reload

    Enable the service:

sudo systemctl enable lohp-server.service

    Start the service:

sudo systemctl start lohp-server.service

    Check status:

sudo systemctl status lohp-server.service

    Reboot to test:

sudo reboot


