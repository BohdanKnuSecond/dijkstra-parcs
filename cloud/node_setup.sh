#!/bin/bash
# Тіло user-data для EC2 (cloud-init виконує від root при першому завантаженні).
# create_cluster.sh дописує зверху змінні ROLE, MASTER, REPO, BRANCH.
set -euo pipefail
exec > >(tee -a /var/log/parcs-setup.log) 2>&1

APP=/opt/lab
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git python3-venv
rm -rf "$APP"
git clone --depth 1 -b "$BRANCH" "$REPO" "$APP"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q -r "$APP/parcs/requirements.txt"

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
systemctl enable --now parcs
echo "PARCS $ROLE started on $IP"
