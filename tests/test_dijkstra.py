# -*- coding: utf-8 -*-
"""Перевірка коректності: Дейкстра проти Флойда-Воршелла, незалежність від N."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'solution'))
import dijkstra_solution as ds  # noqa: E402


def floyd_warshall(adj):
    n = len(adj)
    d = [[ds.INF] * n for _ in range(n)]
    for u in range(n):
        d[u][u] = 0
        for v, w in adj[u]:
            if w < d[u][v]:
                d[u][v] = w
    for k in range(n):
        dk = d[k]
        for i in range(n):
            dik = d[i][k]
            if dik == ds.INF:
                continue
            di = d[i]
            for j in range(n):
                if dik + dk[j] < di[j]:
                    di[j] = dik + dk[j]
    return d


class DijkstraTest(unittest.TestCase):
    def test_matches_floyd_warshall(self):
        for seed in range(1, 8):
            adj = ds.generate_graph(60, 4, 50, seed)
            fw = floyd_warshall(adj)
            for s in range(len(adj)):
                self.assertEqual(ds.dijkstra(adj, s), fw[s], 'seed %d source %d' % (seed, s))

    def test_small_known_graph(self):
        # 0 -1- 1 -2- 2, 0 -5- 2  => dist(0,2) = 3
        adj = [[(1, 1), (2, 5)], [(0, 1), (2, 2)], [(1, 2), (0, 5)]]
        self.assertEqual(ds.dijkstra(adj, 0), [0, 1, 3])

    def test_graph_is_connected_and_deterministic(self):
        a = ds.generate_graph(300, 6, 100, 7)
        b = ds.generate_graph(300, 6, 100, 7)
        self.assertEqual(a, b)
        self.assertNotIn(ds.INF, ds.dijkstra(a, 0))
        edges = sum(len(x) for x in a) // 2
        self.assertEqual(edges, 300 * 6 // 2)

    def test_rng_reference_values(self):
        # фіксовані значення: гарантія однакового графа в Python 2 і 3
        r = ds.SplitMix64(0)
        self.assertEqual([r.next() for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])

    def test_summary_independent_of_parts(self):
        args = (250, 5, 100, 3)
        ref = ds.merge_summaries([ds.solve_part(*(args + (0, 1)))])
        for n in (2, 3, 4, 7):
            got = ds.merge_summaries([ds.solve_part(*(args + (k, n))) for k in range(n)])
            for key in ('sources', 'pairs', 'total', 'max_ecc', 'max_ecc_src',
                        'min_ecc', 'min_ecc_src', 'checksum'):
                self.assertEqual(got[key], ref[key], 'n=%d key=%s' % (n, key))
        self.assertEqual(ref['sources'], 250)
        self.assertEqual(ref['pairs'], 250 * 249)


if __name__ == '__main__':
    unittest.main()
