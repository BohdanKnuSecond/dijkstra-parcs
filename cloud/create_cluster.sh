#!/bin/bash
# Створює правила firewall, master і WORKERS воркерів.
#   bash cloud/create_cluster.sh
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh

[ -n "$PROJECT_ID" ] || { echo "PROJECT_ID не задано"; exit 1; }
case "$REPO_URL" in *CHANGE_ME*) echo "Вкажіть REPO_URL у cloud/config.sh"; exit 1;; esac

gcloud config set project "$PROJECT_ID"
gcloud services enable compute.googleapis.com

# Ноди спілкуються між собою (Flask 8080 + випадкові порти Pyro4) лише всередині VPC
gcloud compute firewall-rules describe parcs-internal >/dev/null 2>&1 || \
  gcloud compute firewall-rules create parcs-internal --network=default \
    --direction=INGRESS --action=ALLOW --rules=tcp,udp,icmp \
    --source-tags=parcs --target-tags=parcs

# Веб-інтерфейс master'а відкриваємо лише для власної IP-адреси
MY_IP="$(curl -fs https://api.ipify.org)"
if gcloud compute firewall-rules describe parcs-ui >/dev/null 2>&1; then
  gcloud compute firewall-rules update parcs-ui --source-ranges="$MY_IP/32"
else
  gcloud compute firewall-rules create parcs-ui --network=default \
    --direction=INGRESS --action=ALLOW --rules=tcp:8080 \
    --source-ranges="$MY_IP/32" --target-tags=parcs-master
fi

COMMON=(--zone="$ZONE" --machine-type="$MACHINE_TYPE"
        --image-family="$IMAGE_FAMILY" --image-project="$IMAGE_PROJECT"
        --boot-disk-size=10GB --metadata-from-file=startup-script=startup.sh)
META="parcs-repo=$REPO_URL,parcs-branch=$REPO_BRANCH,parcs-master=$MASTER_NAME"

gcloud compute instances create "$MASTER_NAME" "${COMMON[@]}" \
  --tags=parcs,parcs-master --metadata="parcs-role=master,$META"

WORKER_NAMES=()
for i in $(seq 1 "$WORKERS"); do WORKER_NAMES+=("$WORKER_PREFIX-$i"); done
gcloud compute instances create "${WORKER_NAMES[@]}" "${COMMON[@]}" \
  --tags=parcs --metadata="parcs-role=worker,$META"

gcloud compute instances list --filter="tags.items=parcs"
MASTER_IP="$(gcloud compute instances describe "$MASTER_NAME" --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
echo
echo "Master UI (через 1-2 хв, поки VM встановлять пакети): http://$MASTER_IP:8080/workers"
