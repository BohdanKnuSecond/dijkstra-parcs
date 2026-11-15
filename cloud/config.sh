# Налаштування кластера PARCS у Google Cloud. Змініть під себе.
# PROJECT_ID можна не задавати — тоді береться з `gcloud config get-value project`.
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-europe-central2}"          # Варшава
ZONE="${ZONE:-europe-central2-a}"
MACHINE_TYPE="${MACHINE_TYPE:-n1-standard-1}" # 1 vCPU: Python-воркер однопотоковий
WORKERS="${WORKERS:-4}"
IMAGE_FAMILY="debian-12"
IMAGE_PROJECT="debian-cloud"

# Публічний репозиторій з цим проєктом (звідси VM беруть код PARCS)
REPO_URL="${REPO_URL:-https://github.com/BohdanKnuSecond/dijkstra-parcs.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"

MASTER_NAME="parcs-master"
WORKER_PREFIX="parcs-worker"
