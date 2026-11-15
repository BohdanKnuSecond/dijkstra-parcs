# -*- coding: utf-8 -*-
"""
Збирання звіту report/Звіт_ЛР1.docx та report/Звіт_ЛР1.pdf з результатів замірів.

  python tools/build_report.py                       # з наявних скріншотів
  python tools/build_report.py --master http://IP:8080   # ще й зняти скріншоти веб-інтерфейсу

Потрібні: python-docx, matplotlib; для PDF — Microsoft Edge (headless).
"""
import argparse
import csv
import html
import os
import re
import statistics
import subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, 'report')
BUILD = os.path.join(REPORT, 'build')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
BENCH = os.path.join(ROOT, 'results', 'aws_bench_v4000.csv')
STATUS = os.path.join(ROOT, 'results', 'aws_cluster_status.txt')
REPO = 'https://github.com/BohdanKnuSecond/dijkstra-parcs'
NAME = 'Звіт_ЛР1_Герасименко'

BLUE = '#2a78d6'
INK = '#1f1f1d'
MUTED = '#6b6a63'
GRID = '#e3e2dc'


# ----------------------------------------------------------------------------
# дані
# ----------------------------------------------------------------------------
def load_bench(path):
    by_n = defaultdict(list)
    meta = {}
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            by_n[int(r['workers'])].append((float(r['time']), float(r['max_compute'])))
            meta = r
    rows = []
    t1 = statistics.median(t for t, _ in by_n[1])
    for n in sorted(by_n):
        times = [t for t, _ in by_n[n]]
        med = statistics.median(times)
        comp = statistics.median(c for _, c in by_n[n])
        s = t1 / med
        rows.append({'n': n, 'med': med, 'min': min(times), 'max': max(times), 'runs': len(times),
                     'compute': comp, 'overhead': med - comp, 'speedup': s, 'eff': s / n})
    return rows, meta


def load_parts(path):
    """Час обчислень кожного воркера з виводу задач: {N: {part: [секунди, ...]}}."""
    parts = defaultdict(lambda: defaultdict(list))
    if not os.path.exists(path):
        return parts
    n = None
    for line in open(path, encoding='utf-8'):
        m = re.match(r'workers\s*:\s*(\d+)', line)
        if m:
            n = int(m.group(1))
        m = re.match(r'\s+(\d+): \d+, [\d.]+, ([\d.]+)$', line)
        if m and n:
            parts[n][int(m.group(1))].append(float(m.group(2)))
    return parts


def make_chart(rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': MUTED,
                         'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED,
                         'text.color': INK})
    ns = [r['n'] for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.5), dpi=200)

    a1.plot(ns, [r['med'] for r in rows], color=BLUE, lw=2, marker='o', ms=7,
            markeredgecolor='white', markeredgewidth=1.5, zorder=3)
    a1.vlines(ns, [r['min'] for r in rows], [r['max'] for r in rows], color=BLUE, lw=1, alpha=.45)
    for r in rows:
        a1.annotate('%.1f с' % r['med'], (r['n'], r['med']), textcoords='offset points',
                    xytext=(8, 6), fontsize=8.5, color=INK)
    a1.set_title('Час виконання, с (медіана з %d запусків)' % rows[0]['runs'], fontsize=9.5, loc='left')
    a1.set_ylim(0, max(r['max'] for r in rows) * 1.15)

    a2.plot(ns, ns, color=MUTED, lw=1.2, ls=(0, (4, 3)), label='ідеальне (S = N)', zorder=2)
    a2.plot(ns, [r['speedup'] for r in rows], color=BLUE, lw=2, marker='o', ms=7,
            markeredgecolor='white', markeredgewidth=1.5, label='виміряне', zorder=3)
    last = rows[-1]
    a2.annotate('%.2f×' % last['speedup'], (last['n'], last['speedup']), textcoords='offset points',
                xytext=(-8, -16), ha='right', fontsize=8.5)
    a2.set_title('Прискорення S(N) = T(1) / T(N)', fontsize=9.5, loc='left')
    a2.set_ylim(0, max(ns) + 0.5)
    a2.legend(frameon=False, fontsize=8.5, loc='upper left')

    for a in (a1, a2):
        a.set_xticks(ns)
        a.set_xlabel('кількість воркерів N')
        a.grid(axis='y', color=GRID, lw=.8)
        a.set_axisbelow(True)
        for s in ('top', 'right'):
            a.spines[s].set_visible(False)
    fig.tight_layout(w_pad=3)
    fig.savefig(path)
    plt.close(fig)


def screenshot(url, path, w=1280, h=640):
    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                    '--window-size=%d,%d' % (w, h), '--screenshot=%s' % path, url],
                   check=True, capture_output=True, timeout=120)


# ----------------------------------------------------------------------------
# зміст звіту: список блоків, з якого рендеряться HTML і DOCX
# ----------------------------------------------------------------------------
def content(rows, meta, status_text, shots, parts):
    r1, rl = rows[0], rows[-1]
    b = []
    P = lambda t: b.append(('p', t))  # noqa: E731

    b.append(('h2', '1. Ідея алгоритму'))
    P('Варіант 1.2 — алгоритм Дейкстри для знаходження найкоротших шляхів. Розв\'язується задача '
      '**найкоротших шляхів між усіма парами вершин** (APSP) зваженого неорієнтованого графа з '
      'невід\'ємними вагами: алгоритм Дейкстри з бінарною купою (`O((V+E)·log V)`) запускається з кожної '
      'вершини. Обходи з різних джерел незалежні, тому задача має природний паралелізм даних '
      '(схема map/reduce):')
    b.append(('ol', [
        '**master** читає параметри: кількість вершин `V`, середній степінь, діапазон ваг, `seed` і кількість '
        'воркерів `N`;',
        'воркер `k` отримує лише ці числа, сам детерміновано генерує той самий граф (власний ГПВЧ SplitMix64 '
        'дає однакову послідовність на будь-якій ноді) і виконує Дейкстру з джерел `k, k+N, k+2N, …` '
        '(циклічний розподіл вирівнює навантаження);',
        'кожен воркер повертає коротке зведення: суму відстаней, ексцентриситети (діаметр, радіус, центр графа) '
        'та контрольну суму своїх рядків матриці відстаней;',
        'master зводить результати (reduce). Виклики воркерів асинхронні (Pyro4), тож усі частини рахуються '
        'одночасно.',
    ]))
    P('Мережею передаються кілька чисел, а не граф чи матриця `V×V`, тому обчислювальна частина '
      '`O(V·(V+E)·log V / N)` домінує над комунікацією і очікуване прискорення близьке до `N`.')
    P('Чому не розпаралелено Дейкстру з одного джерела: вона складається з `V` послідовних кроків, і на '
      'кожному потрібно знайти глобальний мінімум серед усіх воркерів — це `V` мережевих раундів, і на '
      'кластері з окремих VM такий варіант повільніший за послідовний.')
    P('Коректність перевірено тестами (`tests/test_dijkstra.py`): відстані збігаються з алгоритмом '
      'Флойда–Воршелла, а зведення однакове для розбиття на 1, 2, 3, 4 і 7 частин. У хмарі контрольна сума '
      'для V = %s однакова в усіх запусках: `%s`; діаметр графа — %s, радіус — %s.'
      % (meta['vertices'], meta['checksum'], meta['diameter'], meta['radius']))

    b.append(('h2', '2. Платформа PARCS-Python та виправлені помилки'))
    P('За основу взято PARCS-Python (github.com/Hummer12007/parcs-python, останній коміт — 2019 р.). '
      'У поточному вигляді він не збирається й не запускається, тому його портовано на Python 3 '
      '(каталог `parcs/` репозиторію):')
    b.append(('table', ['Проблема', 'Виправлення'], [
        ['Код на Python 2.7: `ConfigParser`, `Queue`, неявні відносні імпорти, `len(filter(...))`',
         'портовано на Python 3'],
        ['`async = Pyro4.async(proxy)` — синтаксична помилка в Python ≥ 3.7; `Pyro4.async` прибрано з Pyro4 4.7x',
         '`proxy._pyroAsync()`'],
        ['Модуль `imp` та `Logger.warn` видалено в Python 3.12/3.13', '`importlib.util`, `log.warning`'],
        ['Dockerfile на `debian:stretch` (EOL, репозиторії apt недоступні), пакет `python-pip` для Python 2',
         'Docker не потрібен: Debian 12 + venv + systemd'],
        ['`get_ip()` шукав лише адреси `192.*` через `netifaces` (у хмарі адреси `172.31.*`/`10.*`; '
         'для нових Python немає wheel)', 'IP визначається через `socket`'],
        ['`py-cpuinfo`: ключ `brand` перейменовано на `brand_raw` (KeyError)', 'виправлено, додано реальний обсяг RAM'],
        ['Поле `RPCThread.daemon` перекривало `Thread.daemon`', 'перейменовано на `pyro_daemon`'],
        ['Залежності без версій у `requirements.txt`', 'версії зафіксовано (Pyro4 4.82, Flask 3)'],
        ['Інструкція відкриває всі порти з `0.0.0.0/0`', 'внутрішній трафік лише між нодами, UI — лише з IP автора'],
    ]))
    P('Додатково додано JSON-ендпоінт `GET /api/job` (статус задач) для автоматизованих замірів.')

    b.append(('h2', '3. Розгортання в хмарі (AWS EC2): інструкція'))
    P('Використано AWS (новий акаунт на Free plan, пробний період Google Cloud уже був використаний). '
      'Обмеження Free plan: роботу дозволено лише в регіоні, обраному при реєстрації (`eu-north-1`, '
      'Стокгольм), і квота 8 vCPU. Усі free-tier типи VM мають 2 vCPU, тож вміщується 4 VM. Тому '
      'на VM `parcs-master` працюють два сервіси — master (порт 8080) і worker-1 (порт 8081), а '
      'worker-2…4 — окремі VM. Master лише роздає задачі та зводить кілька чисел, тому не заважає воркеру.')
    b.append(('table', ['VM', 'Сервіси PARCS', 'Тип', 'Приватна IP'], [
        ['parcs-master', 'master :8080, worker-1 :8081', 't3.micro', status_text.get('parcs-master', '')],
        ['parcs-worker-2', 'worker-2 :8080', 't3.micro', status_text.get('parcs-worker-2', '')],
        ['parcs-worker-3', 'worker-3 :8080', 't3.micro', status_text.get('parcs-worker-3', '')],
        ['parcs-worker-4', 'worker-4 :8080', 't3.micro', status_text.get('parcs-worker-4', '')],
    ]))
    P('Кроки (bash: Linux/macOS, Git Bash на Windows або AWS CloudShell):')
    b.append(('ol', [
        'Встановити AWS CLI v2 і увійти через браузер (ключі доступу не потрібні):',
    ]))
    b.append(('code', 'aws login --region eu-north-1\naws configure set region eu-north-1'))
    b.append(('ol', ['Клонувати репозиторій і створити кластер:'], 2))
    b.append(('code', 'git clone %s.git\ncd dijkstra-parcs\nbash cloud/create_cluster.sh' % REPO))
    P('Скрипт знаходить default VPC, створює security group `parcs-sg` (увесь трафік між нодами групи, '
      'порт 8080 — лише з IP автора) і запускає VM з образом Debian 12. У user-data кожна VM клонує '
      'репозиторій, ставить залежності у venv і запускає PARCS як systemd-сервіс; воркери отримують '
      'приватну IP master\'а при створенні та реєструються в нього самі.')
    b.append(('ol', ['Через 1–3 хв перевірити, що всі воркери підключились:'], 3))
    b.append(('code', 'bash cloud/cluster.sh status      # VM + список воркерів з API master\'а\n'
                      '# веб-інтерфейс: http://<MASTER_PUBLIC_IP>:8080/workers'))
    b.append(('ol', ['Запустити задачу через веб-інтерфейс (Add Job: `solution/dijkstra_solution.py` + '
                     '`solution/input_4000.txt`) або з консолі; параметр `workers=N` у вхідному файлі задає, '
                     'скільки воркерів використати:'], 4))
    b.append(('code', 'python tools/run_job.py --master http://<IP>:8080 run solution/input_4000.txt --workers 2\n'
                      'python tools/run_job.py --master http://<IP>:8080 bench solution/input_4000.txt -n 1 2 3 4 -r 3'))
    b.append(('ol', ['Після роботи зупинити або видалити кластер:'], 5))
    b.append(('code', 'bash cloud/cluster.sh stop     # CPU не тарифікується\nbash cloud/cluster.sh delete   # VM і security group'))
    for path, cap in shots:
        b.append(('img', path, cap))

    b.append(('h2', '4. Результати'))
    P('Умови: граф V = %s вершин, ~%d ребер (середній степінь %s, ваги 1…100, seed %s); VM t3.micro '
      '(Intel Xeon Platinum 8259CL 2,5 ГГц, 2 vCPU, 1 ГБ RAM), Debian 12, Python 3.11, регіон eu-north-1. '
      'Кожну конфігурацію запущено %d рази, у таблиці — медіана, мінімум і максимум. Час вимірює master: '
      'від розсилання задач до отримання всіх результатів.'
      % (meta['vertices'], int(meta['vertices']) * int(meta['degree']) // 2, meta['degree'], meta['seed'],
         r1['runs']))
    b.append(('table', ['Воркерів N', 'Час T(N), с', 'мін…макс, с', 'Обчислення на воркері, с',
                        'Прискорення S', 'Ефективність E'],
              [[str(r['n']), '%.2f' % r['med'], '%.2f…%.2f' % (r['min'], r['max']), '%.2f' % r['compute'],
                '%.2f' % r['speedup'], '%.0f%%' % (r['eff'] * 100)] for r in rows], 'num'))
    b.append(('img', os.path.join(BUILD, 'chart.png'),
              'Рис. %d. Залежність часу виконання (зліва) і прискорення (справа) від кількості воркерів'
              % (len(shots) + 1)))
    P('Час зменшується майже обернено пропорційно кількості воркерів: з %.1f с на одному воркері до %.1f с '
      'на %d (прискорення %.2f×, ефективність %.0f%%). Накладні витрати PARCS (мережа, запуск RPC, '
      'генерація графа на кожній ноді) — різниця між загальним часом і часом обчислень найповільнішого '
      'воркера — становлять лише %.2f…%.2f с, тобто комунікація на результат майже не впливає.'
      % (r1['med'], rl['med'], rl['n'], rl['speedup'], rl['eff'] * 100,
         min(r['overhead'] for r in rows), max(r['overhead'] for r in rows)))
    pn = parts.get(rl['n'])
    if pn:
        med = {k: statistics.median(v) for k, v in pn.items()}
        names = ['worker-1 (VM master)', 'worker-2', 'worker-3', 'worker-4']
        b.append(('table', ['Воркер (N = %d)' % rl['n'], 'Джерел', 'Час обчислень, с (медіана)'],
                  [[names[k] if k < len(names) else str(k), str(int(meta['vertices']) // rl['n']),
                    '%.2f' % med[k]] for k in sorted(med)]))
        avg = statistics.mean(med.values())
        P('Відхилення від ідеалу пояснює нерівна швидкість VM: при однаковій кількості джерел воркери '
          'рахують від %.1f до %.1f с. Середнє — %.1f с, що збігається з T(1)/%d = %.1f с, тобто сама '
          'робота ділиться рівно, а загальний час визначає найповільніша VM. Тип t3.micro — burstable, '
          'фізичне ядро поділене з іншими клієнтами хмари, тому швидкість окремих VM різна. Поліпшити '
          'результат можна динамічним розподілом: ділити джерела на дрібніші порції й видавати їх воркерам '
          'у міру звільнення.'
          % (min(med.values()), max(med.values()), avg, rl['n'], r1['med'] / rl['n']))

    b.append(('h2', '5. Висновки'))
    b.append(('ul', [
        'Обхід Дейкстри з різних джерел незалежний, тому APSP добре масштабується в моделі master/worker '
        'PARCS: на %d воркерах отримано прискорення %.2f×.' % (rl['n'], rl['speedup']),
        'Ключ до масштабованості — мінімальний обсяг комунікації: воркери самі генерують граф за seed і '
        'повертають лише зведення.',
        'PARCS-Python 2019 р. довелося портувати на Python 3 і відмовитись від Docker-образу; розгортання '
        'в AWS повністю автоматизовано скриптами (одна команда створює кластер).',
    ]))

    b.append(('h2', '6. Код'))
    P('Репозиторій: %s' % REPO)
    return b


# ----------------------------------------------------------------------------
# рендеринг
# ----------------------------------------------------------------------------
INLINE = re.compile(r'(\*\*[^*]+\*\*|`[^`]+`)')


def html_inline(text):
    out = []
    for part in INLINE.split(text):
        if part.startswith('**') and part.endswith('**'):
            out.append('<b>%s</b>' % html.escape(part[2:-2]))
        elif part.startswith('`') and part.endswith('`') and len(part) > 1:
            out.append('<code>%s</code>' % html.escape(part[1:-1]))
        else:
            out.append(html.escape(part))
    return ''.join(out)


CSS = """
@page { size: A4; margin: 13mm 14mm 13mm 16mm; }
body { font-family: 'Times New Roman', serif; font-size: 11pt; line-height: 1.3; color: #111; }
h1 { font-size: 15pt; text-align: center; margin: 6px 0 4px; }
h2 { font-size: 12.5pt; margin: 12px 0 5px; border-bottom: 1px solid #888; padding-bottom: 2px; break-after: avoid; }
p { margin: 4px 0 6px; text-align: justify; }
.head { text-align: center; font-size: 10pt; }
code { font-family: Consolas, monospace; font-size: 9.5pt; }
pre { font-family: Consolas, monospace; font-size: 9pt; background: #f4f4f0; padding: 4px 8px; margin: 3px 0 7px;
      white-space: pre-wrap; break-inside: avoid; }
table { border-collapse: collapse; margin: 5px 0 9px; width: 100%; }
tr { break-inside: avoid; }
th, td { border: 1px solid #999; padding: 2px 5px; font-size: 10pt; vertical-align: top; }
th { background: #ececE8; text-align: left; }
table.num td { text-align: right; }
figure { margin: 6px 0 8px; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; border: 1px solid #ddd; }
figcaption { font-size: 9.5pt; color: #333; margin-top: 3px; }
ol, ul { margin: 3px 0 6px 22px; padding: 0; }
li { margin: 2px 0; text-align: justify; }
"""

HEAD_LINES = [
    'Київський національний університет імені Тараса Шевченка · Факультет комп\'ютерних наук та кібернетики',
    'Кафедра теорії та технології програмування · Дисципліна «Хмарні обчислення»',
]
TITLE = ['Звіт з лабораторної роботи № 1', 'Паралельний алгоритм Дейкстри в системі PARCS-Python на AWS']
SIGN = 'Виконав: Герасименко Богдан, група ТТП-41 · Перевірив: А. Васильєв · Київ, 2026'


def render_html(blocks, path):
    h = ['<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>%s</title><style>%s</style>'
         '</head><body>' % (html.escape(TITLE[0]), CSS)]
    h.append('<div class="head">%s</div>' % '<br>'.join(html.escape(x) for x in HEAD_LINES))
    h.append('<h1>%s</h1>' % '<br>'.join(html.escape(x) for x in TITLE))
    h.append('<div class="head">%s</div>' % html.escape(SIGN))
    for blk in blocks:
        kind = blk[0]
        if kind == 'h2':
            h.append('<h2>%s</h2>' % html.escape(blk[1]))
        elif kind == 'p':
            h.append('<p>%s</p>' % html_inline(blk[1]))
        elif kind in ('ol', 'ul'):
            start = ' start="%d"' % blk[2] if len(blk) > 2 else ''
            h.append('<%s%s>%s</%s>' % (kind, start, ''.join('<li>%s</li>' % html_inline(x) for x in blk[1]), kind))
        elif kind == 'code':
            h.append('<pre>%s</pre>' % html.escape(blk[1]))
        elif kind == 'table':
            cls = ' class="num"' if len(blk) > 3 else ''
            h.append('<table%s><tr>%s</tr>%s</table>' % (
                cls, ''.join('<th>%s</th>' % html_inline(c) for c in blk[1]),
                ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % html_inline(c) for c in row) for row in blk[2])))
        elif kind == 'img':
            h.append('<figure><img src="%s"><figcaption>%s</figcaption></figure>'
                     % (os.path.relpath(blk[1], os.path.dirname(path)).replace('\\', '/'), html.escape(blk[2])))
    h.append('</body></html>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(h))


def render_docx(blocks, path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin, sec.right_margin, sec.top_margin, sec.bottom_margin = Cm(2.5), Cm(1.5), Cm(2), Cm(2)
    normal = doc.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
    normal.paragraph_format.space_after = Pt(4)
    for name in ('Heading 1', 'Heading 2'):
        st = doc.styles[name]
        st.font.name = 'Times New Roman'
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.element.rPr.rFonts.set(qn('w:ascii'), 'Times New Roman')
        st.element.rPr.rFonts.set(qn('w:hAnsi'), 'Times New Roman')
    doc.styles['Heading 2'].font.size = Pt(14)
    doc.styles['Heading 1'].font.size = Pt(16)

    def add_runs(par, text, size=None):
        for part in INLINE.split(text):
            if not part:
                continue
            if part.startswith('**') and part.endswith('**'):
                run = par.add_run(part[2:-2])
                run.bold = True
            elif part.startswith('`') and part.endswith('`') and len(part) > 1:
                run = par.add_run(part[1:-1])
                run.font.name = 'Consolas'
                run.font.size = Pt(10.5)
            else:
                run = par.add_run(part)
            if size and not run.font.size:
                run.font.size = Pt(size)

    def centered(text, size, bold=False):
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = par.add_run(text)
        run.font.size = Pt(size)
        run.bold = bold

    for line in HEAD_LINES:
        centered(line, 10.5)
    h = doc.add_heading(level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h.add_run('\n'.join(TITLE))
    centered(SIGN, 11)

    for blk in blocks:
        kind = blk[0]
        if kind == 'h2':
            doc.add_heading(blk[1], level=2)
        elif kind == 'p':
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_runs(par, blk[1])
        elif kind in ('ol', 'ul'):
            start = blk[2] if len(blk) > 2 else 1
            for i, item in enumerate(blk[1]):
                par = doc.add_paragraph()
                par.paragraph_format.left_indent = Cm(0.9)
                par.paragraph_format.first_line_indent = Cm(-0.5)
                par.add_run('%d. ' % (start + i) if kind == 'ol' else '• ')
                add_runs(par, item)
        elif kind == 'code':
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.5)
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:fill'), 'F2F2EE')
            par._p.get_or_add_pPr().append(shd)
            run = par.add_run(blk[1])
            run.font.name = 'Consolas'
            run.font.size = Pt(9.5)
        elif kind == 'table':
            t = doc.add_table(rows=1, cols=len(blk[1]))
            t.style = 'Table Grid'
            for i, c in enumerate(blk[1]):
                cell = t.rows[0].cells[i]
                cell.paragraphs[0].text = ''
                add_runs(cell.paragraphs[0], c, 10.5)
                for r in cell.paragraphs[0].runs:
                    r.bold = True
            for row in blk[2]:
                cells = t.add_row().cells
                for i, c in enumerate(row):
                    add_runs(cells[i].paragraphs[0], c, 10.5)
                    if len(blk) > 3:
                        cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            doc.add_paragraph()
        elif kind == 'img':
            doc.add_picture(blk[1], width=Cm(16.5))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap.add_run(blk[2])
            run.italic = True
            run.font.size = Pt(10.5)
    doc.save(path)


def parse_status(path):
    ips = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            m = re.search(r'(parcs-(?:master|worker-\d))\s*\|\s*([\d.]+)', line)
            if m:
                ips[m.group(1)] = m.group(2)
    return ips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', help='URL master\'а, щоб зняти скріншоти веб-інтерфейсу')
    args = ap.parse_args()
    os.makedirs(BUILD, exist_ok=True)

    shot_workers = os.path.join(REPORT, 'screen_workers.png')
    shot_jobs = os.path.join(REPORT, 'screen_jobs.png')
    if args.master:
        screenshot(args.master.rstrip('/') + '/workers', shot_workers, h=1010)
        screenshot(args.master.rstrip('/') + '/jobs', shot_jobs, h=900)
    shots = []
    if os.path.exists(shot_workers):
        shots.append((shot_workers, 'Рис. 1. Веб-інтерфейс master\'а: 4 підключені воркери (worker-1 — порт 8081 на VM master\'а)'))
    if os.path.exists(shot_jobs):
        shots.append((shot_jobs, 'Рис. %d. Задачі на master\'і: #0 — пробний запуск, #1…#12 — серія замірів N = 1…4' % (len(shots) + 1)))

    rows, meta = load_bench(BENCH)
    make_chart(rows, os.path.join(BUILD, 'chart.png'))
    parts = load_parts(os.path.join(ROOT, 'results', 'aws_bench_v4000_outputs.txt'))
    blocks = content(rows, meta, parse_status(STATUS), shots, parts)

    html_path = os.path.join(BUILD, 'report.html')
    render_html(blocks, html_path)
    docx_path = os.path.join(REPORT, NAME + '.docx')
    render_docx(blocks, docx_path)
    pdf_path = os.path.join(REPORT, NAME + '.pdf')
    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                    '--print-to-pdf=%s' % pdf_path, html_path], check=True, capture_output=True, timeout=120)
    for r in rows:
        print('N=%d  T=%.2f  S=%.2f  E=%.0f%%' % (r['n'], r['med'], r['speedup'], r['eff'] * 100))
    print('OK', docx_path)
    print('OK', pdf_path)


if __name__ == '__main__':
    main()
