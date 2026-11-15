# -*- coding: utf-8 -*-
"""
Паралельний алгоритм Дейкстри для PARCS-Python.

Задача: знайти найкоротші шляхи між усіма парами вершин (APSP) зваженого
неорієнтованого графа, запускаючи алгоритм Дейкстри з кожної вершини.
Обходи з різних джерел незалежні, тому master розподіляє джерела між
воркерами (циклічно: воркер k бере джерела k, k+N, k+2N, ...).

Граф не пересилається мережею: кожен воркер детерміновано генерує його сам
за однаковими параметрами (кількість вершин, середній степінь, seed), тож
мережею йдуть лише кілька чисел туди й коротке зведення назад.

Модуль сумісний з Python 2.7 (на ньому працюють ноди PARCS-Python)
і з Python 3 (для локальної перевірки й тестів).
"""
from __future__ import division, print_function

import heapq
import json
import time

try:
    from Pyro4 import expose
except ImportError:  # локальний запуск без Pyro4
    def expose(obj):
        return obj

MASK64 = (1 << 64) - 1
CHECKSUM_MOD = (1 << 61) - 1
INF = float('inf')


# --------------------------------------------------------------------------
# Генерація графа
# --------------------------------------------------------------------------
class SplitMix64(object):
    """Простий ГПВЧ, що дає однакову послідовність у Python 2 і Python 3."""

    def __init__(self, seed):
        self.state = seed & MASK64

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n


def generate_graph(vertices, degree, max_weight, seed):
    """
    Зв'язний неорієнтований граф зі списками суміжності adj[u] = [(v, w), ...].
    Спочатку випадкове кістякове дерево (гарантує зв'язність), потім
    додаткові випадкові ребра до середнього степеня `degree`.
    """
    rng = SplitMix64(seed)
    adj = [[] for _ in range(vertices)]

    def add_edge(u, v):
        w = 1 + rng.below(max_weight)
        adj[u].append((v, w))
        adj[v].append((u, w))

    for v in range(1, vertices):
        add_edge(v, rng.below(v))

    total_edges = max(vertices - 1, vertices * degree // 2)
    extra = total_edges - (vertices - 1)
    while extra > 0:
        u = rng.below(vertices)
        v = rng.below(vertices)
        if u != v:
            add_edge(u, v)
            extra -= 1
    return adj


# --------------------------------------------------------------------------
# Алгоритм Дейкстри
# --------------------------------------------------------------------------
def dijkstra(adj, source):
    """Класична Дейкстра з бінарною купою (lazy deletion). O((V + E) log V)."""
    dist = [INF] * len(adj)
    dist[source] = 0
    heap = [(0, source)]
    heappop = heapq.heappop
    heappush = heapq.heappush
    while heap:
        d, u = heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heappush(heap, (nd, v))
    return dist


def empty_summary():
    return {
        'sources': 0,
        'pairs': 0,               # кількість досяжних пар (s, v), s != v
        'total': 0,               # сума всіх найкоротших відстаней
        'max_ecc': -1,            # максимальний ексцентриситет = діаметр
        'max_ecc_src': -1,
        'min_ecc': -1,            # мінімальний ексцентриситет = радіус
        'min_ecc_src': -1,        # вершина-центр
        'checksum': 0,            # контрольна сума всієї матриці відстаней
    }


def summarize_source(summary, source, dist):
    """Додає результат обходу з однієї вершини до зведення."""
    ecc = 0
    row_sum = 0
    row_hash = 0
    reached = 0
    for v, d in enumerate(dist):
        if d == INF or v == source:
            continue
        d = int(d)
        reached += 1
        row_sum += d
        row_hash = (row_hash + d * (v + 1)) % CHECKSUM_MOD
        if d > ecc:
            ecc = d
    summary['sources'] += 1
    summary['pairs'] += reached
    summary['total'] += row_sum
    summary['checksum'] = (summary['checksum'] + row_hash * (source + 1)) % CHECKSUM_MOD
    if ecc > summary['max_ecc'] or (ecc == summary['max_ecc'] and source < summary['max_ecc_src']):
        summary['max_ecc'], summary['max_ecc_src'] = ecc, source
    if summary['min_ecc'] < 0 or ecc < summary['min_ecc'] or \
            (ecc == summary['min_ecc'] and source < summary['min_ecc_src']):
        summary['min_ecc'], summary['min_ecc_src'] = ecc, source


def merge_summaries(parts):
    total = empty_summary()
    for p in parts:
        if p['sources'] == 0:
            continue
        total['sources'] += p['sources']
        total['pairs'] += p['pairs']
        total['total'] += p['total']
        total['checksum'] = (total['checksum'] + p['checksum']) % CHECKSUM_MOD
        if p['max_ecc'] > total['max_ecc'] or \
                (p['max_ecc'] == total['max_ecc'] and p['max_ecc_src'] < total['max_ecc_src']):
            total['max_ecc'], total['max_ecc_src'] = p['max_ecc'], p['max_ecc_src']
        if total['min_ecc'] < 0 or p['min_ecc'] < total['min_ecc'] or \
                (p['min_ecc'] == total['min_ecc'] and p['min_ecc_src'] < total['min_ecc_src']):
            total['min_ecc'], total['min_ecc_src'] = p['min_ecc'], p['min_ecc_src']
    return total


def solve_part(vertices, degree, max_weight, seed, part, parts):
    """
    Робота одного воркера: згенерувати граф і виконати Дейкстру з джерел
    part, part + parts, part + 2*parts, ...
    """
    t0 = time.time()
    adj = generate_graph(vertices, degree, max_weight, seed)
    t1 = time.time()
    summary = empty_summary()
    for source in range(part, vertices, parts):
        summarize_source(summary, source, dijkstra(adj, source))
    t2 = time.time()
    summary['part'] = part
    summary['gen_time'] = round(t1 - t0, 4)
    summary['compute_time'] = round(t2 - t1, 4)
    return summary


def read_params(path):
    params = {'vertices': 2000, 'degree': 10, 'max_weight': 100, 'seed': 42, 'workers': 0}
    with open(path) as f:
        for line in f:
            line = line.split('#', 1)[0].strip()
            if not line or '=' not in line:
                continue
            key, value = [x.strip() for x in line.split('=', 1)]
            params[key] = int(value)
    return params


# --------------------------------------------------------------------------
# PARCS Solver
# --------------------------------------------------------------------------
class Solver:
    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.workers = workers
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name

    def solve(self):
        p = read_params(self.input_file_name)
        available = len(self.workers)
        n = p['workers'] if 0 < p['workers'] <= available else available
        workers = self.workers[:n]
        print('Dijkstra APSP: V=%d, degree=%d, workers used %d of %d'
              % (p['vertices'], p['degree'], n, available))

        t0 = time.time()
        # map: проксі Pyro4 у PARCS асинхронні, тож виклики стартують одночасно
        futures = [w.run_part(p['vertices'], p['degree'], p['max_weight'], p['seed'], k, n)
                   for k, w in enumerate(workers)]
        parts = [f.value if hasattr(f, 'value') else f for f in futures]
        # reduce
        result = merge_summaries(parts)
        elapsed = time.time() - t0

        self.write_output(p, n, available, elapsed, result, parts)
        print('Done in %.3f s' % elapsed)

    @expose
    def run_part(self, vertices, degree, max_weight, seed, part, parts):
        return solve_part(vertices, degree, max_weight, seed, part, parts)

    def write_output(self, p, n, available, elapsed, result, parts):
        lines = [
            'Parallel Dijkstra (all-pairs shortest paths) on PARCS-Python',
            'vertices      : %d' % p['vertices'],
            'edges         : ~%d (avg degree %d, weights 1..%d, seed %d)'
            % (max(p['vertices'] - 1, p['vertices'] * p['degree'] // 2),
               p['degree'], p['max_weight'], p['seed']),
            'workers       : %d (available %d)' % (n, available),
            'time, s       : %.3f' % elapsed,
            '',
            'reachable pairs : %d' % result['pairs'],
            'sum of distances: %d' % result['total'],
            'avg distance    : %.4f' % (result['total'] / max(1, result['pairs'])),
            'diameter        : %d (from vertex %d)' % (result['max_ecc'], result['max_ecc_src']),
            'radius          : %d (center vertex %d)' % (result['min_ecc'], result['min_ecc_src']),
            'checksum        : %d' % result['checksum'],
            '',
            'per worker (part: sources, gen s, compute s):',
        ]
        for part in sorted(parts, key=lambda x: x['part']):
            lines.append('  %d: %d, %.3f, %.3f'
                         % (part['part'], part['sources'], part['gen_time'], part['compute_time']))
        record = {'vertices': p['vertices'], 'degree': p['degree'], 'seed': p['seed'],
                  'workers': n, 'time': round(elapsed, 4), 'checksum': result['checksum'],
                  'diameter': result['max_ecc'], 'radius': result['min_ecc'],
                  'max_compute': max(x['compute_time'] for x in parts)}
        lines.append('')
        lines.append('RESULT_JSON ' + json.dumps(record, sort_keys=True))
        with open(self.output_file_name, 'w') as f:
            f.write('\n'.join(lines) + '\n')
