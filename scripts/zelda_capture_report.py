#!/usr/bin/env python3
"""Read an existing DM_NVN_TSV capture and print sanitized numeric aggregates.

Does not launch a game, alter files, build shaders or reproduce raw log text.
Timing alone cannot establish correct graphics, stable gameplay or memory safety.
"""
import argparse
import json
import math

METRICS = ('@frame_ms', '@presented_ms', '@gpu_ms', '@submit_ms', '@sync_ms', '@work_ms')


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally repeats rejected argv, which may contain private paths.
        self.exit(2, 'Invalid arguments; use --help for capture-report usage.\n')


def percentile(values, p):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * p) - 1)] if values else None


def summarize(lines, budget_ms=1000 / 30):
    if not math.isfinite(budget_ms) or budget_ms <= 0:
        raise ValueError('invalid frame budget')
    rows, invalid = {}, 0
    for line in lines:
        fields = line.rstrip('\r\n').split('\t')
        if len(fields) != 3 or fields[1] not in (*METRICS, '@t_s'):
            continue
        try:
            frame, value = int(fields[0]), float(fields[2])
            if frame < 0 or not math.isfinite(value):
                raise ValueError
        except ValueError:
            invalid += 1
            continue
        row = rows.setdefault(frame, {})
        if fields[1] == '@t_s' and '@t_s' in row and row['@t_s'] != value:
            raise ValueError('conflicting capture timestamps')
        row[fields[1]] = value  # delayed GPU/present rows belong to their frame
    selected = [(f, r) for f, r in sorted(rows.items()) if r.get('@t_s', -1) >= 0]
    if not selected:
        raise ValueError('no timestamped frames')
    times = [r['@t_s'] for _, r in selected]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('timestamps are not strictly increasing; use one capture per report')
    span = times[-1] - times[0]
    contiguous = all(b[0] == a[0] + 1 for a, b in zip(selected, selected[1:]))
    rate = (len(selected) - 1) / span if span > 0 and contiguous else None
    if rate is not None and not math.isfinite(rate):
        raise ValueError('timestamp interval cannot produce a finite frame rate')
    metrics = {}
    for metric in METRICS:
        values = [r[metric] for _, r in selected if metric in r and
                  (r[metric] > 0 if metric in ('@frame_ms', '@presented_ms') else r[metric] >= 0)]
        metrics[metric[1:]] = {'samples': len(values), 'p50': percentile(values, .50),
                              'p95': percentile(values, .95), 'p99': percentile(values, .99),
                              'max': max(values) if values else None}
    return {'timestamped_frames': len(selected), 'observed_span_s': span,
            'duration_gate_1200s_met': span >= 1200,
            'frame_ids_contiguous': contiguous,
            'observed_frame_rate': rate,
            'frame_budget_ms': budget_ms,
            'over_budget_frames': sum(r.get('@frame_ms', 0) > budget_ms for _, r in selected),
            'dropped_presentations': sum(r.get('@presented_ms') == -1 for _, r in selected),
            'invalid_numeric_rows': invalid, 'metrics': metrics,
            'unmeasured': ['visual correctness', 'audio', 'termination cause', 'footprint', 'swap',
                           'residency', 'staging churn', 'thermal state', 'internal resolution']}


def main():
    parser = SafeParser(prog='zelda_capture_report', description=__doc__)
    parser.add_argument('capture')
    parser.add_argument('--budget-ms', type=float, default=1000 / 30)
    args = parser.parse_args()
    try:
        with open(args.capture, encoding='utf-8', errors='replace') as stream:
            result = summarize(stream, args.budget_ms)
    except (OSError, ValueError):
        # Never reproduce private input paths, text or exception values.
        parser.exit(2, 'Cannot summarize capture: unreadable file or invalid timing data.\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
