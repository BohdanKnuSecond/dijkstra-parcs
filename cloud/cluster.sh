#!/bin/bash
# Керування кластером:
#   bash cloud/cluster.sh status   # VM + зареєстровані воркери
#   bash cloud/cluster.sh ip       # зовнішня IP master'а
#   bash cloud/cluster.sh stop     # зупинити VM (не платимо за CPU)
#   bash cloud/cluster.sh start    # запустити знову
#   bash cloud/cluster.sh delete   # видалити VM і правила firewall
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh

NAMES=("$MASTER_NAME")
for i in $(seq 1 "$WORKERS"); do NAMES+=("$WORKER_PREFIX-$i"); done

master_ip() {
  gcloud compute instances describe "$MASTER_NAME" --zone="$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
}

case "${1:-status}" in
  status)
    gcloud compute instances list --filter="tags.items=parcs" \
      --format="table(name,zone.basename(),machineType.basename(),networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP,status)"
    echo
    curl -fs "http://$(master_ip):8080/api/worker" || echo "master ще не відповідає"
    echo ;;
  ip) master_ip ;;
  stop) gcloud compute instances stop "${NAMES[@]}" --zone="$ZONE" ;;
  start)
    gcloud compute instances start "${NAMES[@]}" --zone="$ZONE"
    # зовнішня IP змінюється після зупинки — оновлюємо доступ до UI для поточної адреси
    gcloud compute firewall-rules update parcs-ui --source-ranges="$(curl -fs https://api.ipify.org)/32"
    echo "Master: http://$(master_ip):8080/workers" ;;
  delete)
    gcloud compute instances delete "${NAMES[@]}" --zone="$ZONE" --quiet
    gcloud compute firewall-rules delete parcs-internal parcs-ui --quiet ;;
  *) echo "usage: $0 status|ip|stop|start|delete"; exit 1 ;;
esac
