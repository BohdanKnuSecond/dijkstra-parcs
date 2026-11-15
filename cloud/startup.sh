#!/bin/bash
# Startup-script для VM (виконується від root при кожному завантаженні).
# Роль ноди та адреса master'а передаються через метадані інстансу.
set -euo pipefail

md() {
  curl -fs -H 'Metadata-Flavor: Google' \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}

ROLE="$(md parcs-role)"            # master | worker
MASTER="$(md parcs-master || true)" # ім'я master-VM (внутрішній DNS GCP)
REPO="$(md parcs-repo)"
BRANCH="$(md parcs-branch || echo main)"
APP=/opt/lab

if [ ! -x "$APP/.venv/bin/python" ]; then
  apt-get update -q
  apt-get install -y -q git python3-venv
  rm -rf "$APP"
  git clone --depth 1 -b "$BRANCH" "$REPO" "$APP"
  python3 -m venv "$APP/.venv"
  "$APP/.venv/bin/pip" install -q -r "$APP/parcs/requirements.txt"
fi

IP="$(hostname -I | awk '{print $1}')"
if [ "$ROLE" = "master" ]; then
  ARGS="-ip $IP -port 8080"
else
  ARGS="-ip $IP -port 8080 -master_ip $MASTER -master_port 8080"
fi

cat > /etc/systemd/system/parcs.service <<EOF
[Unit]
Description=PARCS-Python $ROLE node
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP/parcs
ExecStart=$APP/.venv/bin/python start.py $ARGS
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable parcs
systemctl restart parcs
echo "PARCS $ROLE started on $IP"
