# -*- coding: utf-8 -*-
"""
Локальний кластер PARCS для налагодження: master + N воркерів як окремі процеси
на 127.0.0.1 (без Docker/WSL). Зупинка — Ctrl+C.

  python tools/local_cluster.py --workers 4
"""
import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARCS = os.path.join(ROOT, 'parcs')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--master-port', type=int, default=8080)
    ap.add_argument('--log-dir', default=os.path.join(ROOT, 'results', 'local_logs'))
    args = ap.parse_args()
    os.makedirs(args.log_dir, exist_ok=True)

    procs = []

    def spawn(name, extra):
        log = open(os.path.join(args.log_dir, name + '.log'), 'w')
        p = subprocess.Popen([sys.executable, 'start.py', '-ip', '127.0.0.1'] + extra,
                             cwd=PARCS, stdout=log, stderr=subprocess.STDOUT)
        procs.append(p)
        print('started %s (pid %d)' % (name, p.pid))

    spawn('master', ['-port', str(args.master_port)])
    time.sleep(2)
    for i in range(1, args.workers + 1):
        spawn('worker-%d' % i, ['-port', str(args.master_port + i),
                                '-master_ip', '127.0.0.1', '-master_port', str(args.master_port)])
    print('master UI: http://127.0.0.1:%d/workers' % args.master_port)
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        print('a node exited, see logs in %s' % args.log_dir)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()


if __name__ == '__main__':
    main()
