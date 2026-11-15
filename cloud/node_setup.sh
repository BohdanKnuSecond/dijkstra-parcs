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

service() {  # $1 = ім'я сервісу, $2 = опис, $3 = аргументи start.py
  cat > "/etc/systemd/system/$1.service" <<EOF
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP/parcs
ExecStart=$APP/.venv/bin/python start.py $3
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now "$1"
}

if [ "$ROLE" = "master" ]; then
  service parcs-master "PARCS-Python master node" "-ip $IP -port 8080"
  # Квота 8 vCPU на Free plan: master легкий, тож на тій самій VM (2 vCPU) працює worker-1
  if [ "${COLOCATED_WORKER:-0}" = "1" ]; then
    service parcs-worker "PARCS-Python worker node" "-ip $IP -port 8081 -master_ip $IP -master_port 8080"
  fi
else
  service parcs-worker "PARCS-Python worker node" "-ip $IP -port 8080 -master_ip $MASTER -master_port 8080"
fi
echo "PARCS $ROLE started on $IP"
