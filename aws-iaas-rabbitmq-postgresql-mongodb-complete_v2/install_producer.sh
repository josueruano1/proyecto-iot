#!/bin/bash
set -euo pipefail

sudo dnf update -y
sudo dnf install -y python3 python3-pip git

mkdir -p /opt/synthetic-producer
cd /opt/synthetic-producer

cat <<'EOF' > main.py
${producer_main_py}
EOF

cat <<'EOF' > config.py
${producer_config_py}
EOF

cat <<'EOF' > scenarios.py
${producer_scenarios_py}
EOF

cat <<'EOF' > requirements.txt
${producer_requirements_txt}
EOF

cat <<'EOF' > /opt/synthetic-producer/.env
POLL_INTERVAL_SECONDS=3
CYCLE_INTERVAL_SECONDS=15
TASK_POLL_ATTEMPTS=20
EOF

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

cat <<'EOF' | sudo tee /etc/systemd/system/synthetic-producer.service >/dev/null
[Unit]
Description=Synthetic Event Producer
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/synthetic-producer
EnvironmentFile=/opt/synthetic-producer/.env
ExecStart=/usr/bin/python3 /opt/synthetic-producer/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable synthetic-producer
sudo systemctl restart synthetic-producer