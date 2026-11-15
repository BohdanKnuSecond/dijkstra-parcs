# -*- coding: utf-8 -*-
"""
Клієнт PARCS master'а (лише стандартна бібліотека Python 3).

  # список воркерів
  python tools/run_job.py --master http://IP:8080 workers

  # одна задача
  python tools/run_job.py --master http://IP:8080 run solution/input_4000.txt --workers 2

  # серія для звіту: N = 1..4, по 3 повтори, результат у results/*.csv
  python tools/run_job.py --master http://IP:8080 bench solution/input_4000.txt -n 1 2 3 4 -r 3
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLUTION = os.path.join(ROOT, 'solution', 'dijkstra_solution.py')


def http(method, url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def multipart(fields, files):
    boundary = uuid.uuid4().hex
    out = []
    for name, value in fields.items():
        out.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                    % (boundary, name, value)).encode())
    for name, (filename, content) in files.items():
        out.append(('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                    'Content-Type: application/octet-stream\r\n\r\n' % (boundary, name, filename)).encode())
        out.append(content + b'\r\n')
    out.append(('--%s--\r\n' % boundary).encode())
    return b''.join(out), 'multipart/form-data; boundary=%s' % boundary


def list_workers(master):
    _, body = http('GET', master + '/api/worker')
    return json.loads(body)['workers']


def submit(master, input_text, name):
    body, ctype = multipart({'job_name': name}, {
        'solution_file': ('solution.py', open(SOLUTION, 'rb').read()),
        'input_file': ('input.txt', input_text.encode()),
    })
    _, resp = http('POST', master + '/api/job?format=json', body, {'Content-Type': ctype})
    return json.loads(resp)['job']['id']


def wait(master, job_id, poll=1.0, timeout=3600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, body = http('GET', master + '/api/job')
        job = [j for j in json.loads(body)['jobs'] if j['id'] == job_id][0]
        if job['ended']:
            if job['failed']:
                raise RuntimeError('job %d failed: %s' % (job_id, job['status']))
            _, out = http('GET', '%s/api/job/%d/output' % (master, job_id))
            return out.decode()
        time.sleep(poll)
    raise TimeoutError('job %d timeout' % job_id)


def make_input(path, workers):
    text = open(path).read()
    text = re.sub(r'^\s*workers\s*=.*$', '', text, flags=re.M).rstrip() + '\n'
    return text + 'workers=%d\n' % workers


def parse_result(output):
    for line in output.splitlines():
        if line.startswith('RESULT_JSON '):
            return json.loads(line[len('RESULT_JSON '):])
    raise ValueError('no RESULT_JSON in output')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', default='http://127.0.0.1:8080')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('workers')
    r = sub.add_parser('run')
    r.add_argument('input')
    r.add_argument('--workers', type=int, default=0, help='0 = усі')
    b = sub.add_parser('bench')
    b.add_argument('input')
    b.add_argument('-n', type=int, nargs='+', default=[1, 2, 3, 4])
    b.add_argument('-r', '--repeats', type=int, default=3)
    b.add_argument('--out', default=None)
    args = ap.parse_args()
    master = args.master.rstrip('/')

    if args.cmd == 'workers':
        for w in list_workers(master):
            print('#%d %s:%d enabled=%s  %s, RAM %s' % (w['id'], w['ip'], w['port'], w['enabled'],
                                                        w['info']['cpu'], w['info']['ram']))
        return

    if args.cmd == 'run':
        job = submit(master, make_input(args.input, args.workers), 'dijkstra-n%d' % args.workers)
        print('job #%d submitted' % job)
        print(wait(master, job))
        return

    available = len(list_workers(master))
    print('available workers: %d' % available)
    rows = []
    for n in args.n:
        if n > available:
            print('skip N=%d (only %d workers)' % (n, available))
            continue
        for rep in range(1, args.repeats + 1):
            job = submit(master, make_input(args.input, n), 'dijkstra-n%d-r%d' % (n, rep))
            res = parse_result(wait(master, job))
            res.update({'job': job, 'repeat': rep})
            rows.append(res)
            print('N=%d rep=%d time=%.3fs checksum=%d' % (res['workers'], rep, res['time'], res['checksum']))
            sys.stdout.flush()

    if len({r['checksum'] for r in rows}) > 1:
        print('WARNING: checksums differ between runs!')
    out = args.out or os.path.join(ROOT, 'results', 'bench_%s.csv' % time.strftime('%Y%m%d_%H%M%S'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    keys = ['workers', 'repeat', 'time', 'max_compute', 'vertices', 'degree', 'seed',
            'checksum', 'diameter', 'radius', 'job']
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('saved %s' % out)


if __name__ == '__main__':
    main()
