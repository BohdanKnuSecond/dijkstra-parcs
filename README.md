# Паралельний алгоритм Дейкстри на PARCS-Python в AWS

Лабораторна робота №1 з курсу «Хмарні обчислення», варіант 1.2:
**алгоритм Дейкстри для знаходження найкоротших шляхів**.

## Ідея

Шукаємо найкоротші відстані між **усіма парами вершин** (APSP) зваженого неорієнтованого графа,
запускаючи Дейкстру (бінарна купа, `O((V+E) log V)`) з кожної вершини. Обходи з різних джерел
повністю незалежні, тож це задача з природним паралелізмом даних:

1. **master** читає параметри (`V`, середній степінь, діапазон ваг, `seed`, кількість воркерів `N`);
2. воркер `k` отримує лише числа `(V, degree, max_weight, seed, k, N)`, сам детерміновано генерує
   той самий граф (власний ГПВЧ SplitMix64, однаковий у будь-якому Python) і виконує Дейкстру
   з джерел `k, k+N, k+2N, …`;
3. кожен воркер повертає коротке зведення: суму відстаней, ексцентриситети (діаметр, радіус, центр)
   та контрольну суму рядків матриці відстаней;
4. master зводить результати (reduce). Контрольна сума не залежить від `N`, тож правильність
   паралельного запуску перевіряється порівнянням із послідовним.

Мережею передаються кілька чисел, а не граф чи матриця `V×V`, тому прискорення близьке до лінійного.

Чому не паралелимо саму Дейкстру з одного джерела: вона складається з `V` послідовних кроків, і на
кожному треба знайти глобальний мінімум серед усіх воркерів, тобто `V` мережевих раундів. На
кластері з окремих VM такий варіант працює повільніше за послідовний.

## Структура

| Шлях | Що це |
|---|---|
| `solution/dijkstra_solution.py` | модуль задачі PARCS (`Solver`), завантажується на master |
| `solution/input_*.txt` | вхідні параметри |
| `sequential.py` | послідовна версія (еталон) |
| `tests/` | тести: Дейкстра проти Флойда-Воршелла, незалежність результату від `N` |
| `parcs/` | PARCS-Python, портований на Python 3 (див. нижче) |
| `cloud/` | скрипти розгортання в AWS EC2 |
| `tools/run_job.py` | клієнт: запуск задач і серій замірів через HTTP API master'а |
| `tools/local_cluster.py` | локальний кластер (master + N воркерів як процеси) для налагодження |

## PARCS-Python: що довелося виправити

За основу взято [Hummer12007/parcs-python](https://github.com/Hummer12007/parcs-python) (останній
коміт 2019 р.). Він не запускається на сучасному ПЗ:

| Проблема | Виправлення |
|---|---|
| Код на Python 2.7 (`ConfigParser`, `Queue`, неявні відносні імпорти, `len(filter(...))`) | портовано на Python 3 |
| `async = Pyro4.async(proxy)` — синтаксична помилка в Python ≥ 3.7, а `Pyro4.async` прибрано з Pyro4 4.7x | `proxy._pyroAsync()` |
| модуль `imp` і `Logger.warn` видалено в Python 3.12/3.13 | `importlib.util`, `log.warning` |
| Dockerfile на `debian:stretch` (EOL, репозиторії apt недоступні), `python-pip` для Python 2 | Docker не використовується: Debian 12 + venv + systemd |
| інструкція з `gcloud compute instances create-with-container` (Docker-образ 2019 р.) застаріла | звичайні VM з Debian 12 + user-data (див. нижче) |
| `get_ip()` шукав лише адреси `192.*` через `netifaces` (у GCP `10.*`; немає wheel для нових Python) | IP через `socket` |
| `py-cpuinfo`: ключ `brand` → `brand_raw` | виправлено, додано реальний обсяг RAM |
| поле `RPCThread.daemon` перекривало `Thread.daemon` | перейменовано на `pyro_daemon` |
| неповні залежності в `requirements.txt` | версії зафіксовано |
| firewall `allow-all` з `0.0.0.0/0` | внутрішній трафік лише між нодами, UI лише з вашої IP |

Також додано JSON-ендпоінт `GET /api/job` (статус задач) для автоматизованих замірів.

## Локальний запуск

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r parcs/requirements.txt   # Linux/macOS: .venv/bin/...
python -m unittest discover -s tests
python sequential.py solution/input_2000.txt
.venv/Scripts/python tools/local_cluster.py --workers 4          # в окремому терміналі
.venv/Scripts/python tools/run_job.py bench solution/input_2000.txt -n 1 2 3 4 -r 2
```

## Розгортання в AWS EC2

Потрібні: акаунт AWS (новий акаунт на Free plan підходить), [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
і bash (Linux/macOS, Git Bash на Windows або AWS CloudShell).

```bash
aws login --region eu-north-1    # вхід через браузер, ключі доступу не потрібні
aws configure set region eu-north-1   # Free plan працює лише в регіоні, обраному при реєстрації
```

У `cloud/config.sh` за потреби змініть `REPO_URL` (публічний форк цього репозиторію), регіон і тип VM.
Кожна нода — окрема VM з Debian 12; user-data клонує репозиторій, ставить залежності у venv
і запускає PARCS як systemd-сервіс. Воркери отримують приватну IP master'а при створенні.

```bash
bash cloud/create_cluster.sh     # security group + parcs-master + parcs-worker-1..4
bash cloud/cluster.sh status     # VM і зареєстровані воркери (через 2-3 хв після створення)
```

Новий акаунт на Free plan має квоту 8 vCPU, а всі free-tier типи (`t3.micro` тощо) мають по 2 vCPU,
тобто вміщується 4 VM. Тому за замовчуванням (`COLOCATED_WORKER=1`) на VM `parcs-master` працюють
два сервіси — master (порт 8080) і worker-1 (порт 8081), а `parcs-worker-2..4` — окремі VM.
Master лише роздає задачі й зводить результати, тож не заважає воркеру. Якщо квота дозволяє
5+ VM: `COLOCATED_WORKER=0 bash cloud/create_cluster.sh`.

Веб-інтерфейс: `http://<MASTER_IP>:8080/workers`. Задачу можна додати через UI (Add Job:
`solution/dijkstra_solution.py` + `solution/input_4000.txt`) або з консолі:

```bash
python tools/run_job.py --master http://<MASTER_IP>:8080 run solution/input_4000.txt --workers 2
python tools/run_job.py --master http://<MASTER_IP>:8080 bench solution/input_4000.txt -n 1 2 3 4 -r 3
```

Параметр `workers=N` у вхідному файлі задає, скільки з підключених воркерів використати (`0` = усі).

Після роботи:

```bash
bash cloud/cluster.sh stop       # зупинити (диски лишаються, CPU не тарифікується)
bash cloud/cluster.sh delete     # видалити все
```

## Результати

_Буде заповнено після замірів у хмарі._
