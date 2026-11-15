# -*- coding: utf-8 -*-
"""
Послідовна версія (еталон): той самий граф і та сама Дейкстра з кожної вершини
в одному процесі, без PARCS. Також може імітувати розбиття на N частин,
щоб перевірити, що зведення не залежить від кількості воркерів.

    python sequential.py solution/input_2000.txt
    python sequential.py solution/input_2000.txt --parts 4
"""
from __future__ import print_function

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import dijkstra_solution as ds  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--parts', type=int, default=1, help='імітувати розбиття на N частин')
    args = ap.parse_args()

    p = ds.read_params(args.input)
    t0 = time.time()
    parts = [ds.solve_part(p['vertices'], p['degree'], p['max_weight'], p['seed'], k, args.parts)
             for k in range(args.parts)]
    result = ds.merge_summaries(parts)
    elapsed = time.time() - t0

    print('V=%d degree=%d seed=%d parts=%d' % (p['vertices'], p['degree'], p['seed'], args.parts))
    print('time, s   : %.3f' % elapsed)
    print('pairs     : %d' % result['pairs'])
    print('sum dist  : %d' % result['total'])
    print('diameter  : %d (from %d)' % (result['max_ecc'], result['max_ecc_src']))
    print('radius    : %d (center %d)' % (result['min_ecc'], result['min_ecc_src']))
    print('checksum  : %d' % result['checksum'])


if __name__ == '__main__':
    main()
