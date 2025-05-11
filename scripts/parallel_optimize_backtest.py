#!/usr/bin/env python3
"""
Parallel optimize backtest wrapper with dynamic scanning only.
Runs backtest.py combos in parallel and writes summary.csv.
"""
import os
import sys
import argparse
import itertools
import subprocess
import csv
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor


def parse_args():
    parser = argparse.ArgumentParser(
        description="Parallel backtest optimizer with dynamic scanning only"
    )
    parser.add_argument('--tickers', required=True, help='Comma-separated tickers (overridden in dynamic scan mode)')
    parser.add_argument('--start', required=True, help='Backtest start date YYYY-MM-DD')
    parser.add_argument('--end', required=True, help='Backtest end date YYYY-MM-DD')
    parser.add_argument(
        '--output-dir',
        default=os.getenv('OPTIMIZE_OUTPUT_DIR', 'outputs/optimize/dynamic'),
        help='Base dir for all runs [env: OPTIMIZE_OUTPUT_DIR]'
    )
    parser.add_argument(
        '--iv-thresholds', nargs='+', type=float,
        default=[0.2, 0.25, 0.3], help='List of IV thresholds to test'
    )
    parser.add_argument(
        '--end-buffer-minutes', nargs='+', type=int,
        default=[5, 10, 15], help='List of end-buffer minutes'
    )
    parser.add_argument(
        '--initial-capitals', nargs='+', type=float,
        default=[100000.0], help='List of starting capitals'
    )
    parser.add_argument(
        '--ml-flags', nargs='+', type=lambda v: v.lower() in ('true','1'),
        default=[False, True], help='Enable/disable ML toggle values'
    )
    parser.add_argument(
        '--risk-flags', nargs='+', type=lambda v: v.lower() in ('true','1'),
        default=[False, True], help='Enable/disable risk management toggle values'
    )
    parser.add_argument(
        '--news-flags', nargs='+', type=lambda v: v.lower() in ('true','1'),
        default=[False, True], help='Enable/disable news risk toggle values'
    )
    parser.add_argument(
        '--workers', type=int, default=None,
        help='Number of parallel workers (default: CPU count)'
    )
    return parser.parse_args()


def run_combo(combo, args, base_output):
    iv, eb, ic, enable_ml, enable_scan, enable_risk, enable_news = combo
    combo_name = f"iv{iv}_eb{eb}_ic{int(ic)}"
    combo_dir = base_output / combo_name
    combo_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, 'backtest.py',
        '--tickers', args.tickers,
        '--start', args.start,
        '--end', args.end,
        '--iv-threshold', str(iv),
        '--end-buffer-minutes', str(eb),
        '--initial-capital', str(ic),
        '--output-dir', str(combo_dir)
    ]
    # dynamic scanning always on
    cmd.append('--enable-scanning')
    # ML toggle
    cmd.append('--enable-ml' if enable_ml else '--disable-ml')
    # risk management toggle
    cmd.append('--enable-risk-management' if enable_risk else '--disable-risk-management')
    # news risk toggle
    cmd.append('--enable-news-risk' if enable_news else '--disable-news-risk')

    print(f"Running {combo_name}, ML={enable_ml}, Scan=on, Risk={enable_risk}, News={enable_news}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error in combo {combo_name}: {result.stderr.strip()}", file=sys.stderr)
        net_pl = None
    else:
        run_id = f"{args.start}_to_{args.end}_{args.tickers.replace(',','_')}"
        results_path = combo_dir / run_id / 'results_csv'
        csv_files = list(results_path.glob('*.csv'))
        if csv_files:
            import pandas as pd
            df = pd.read_csv(csv_files[0])
            net_pl = df['pl'].sum()
        else:
            net_pl = 0.0
    return iv, eb, ic, enable_ml, True, enable_risk, enable_news, net_pl


def main():
    args = parse_args()
    base_output = Path(args.output_dir)
    base_output.mkdir(parents=True, exist_ok=True)

    # build combo grid
    combos = list(itertools.product(
        args.iv_thresholds,
        args.end_buffer_minutes,
        args.initial_capitals,
        args.ml_flags,
        [True],  # dynamic scanning only
        args.risk_flags,
        args.news_flags
    ))

    # determine number of workers
    workers = args.workers or os.cpu_count() or 1
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(run_combo, combo, args, base_output) for combo in combos]
            results = [f.result() for f in futures]
    else:
        results = [run_combo(combo, args, base_output) for combo in combos]

    # write summary
    summary_csv = base_output / 'summary.csv'
    with summary_csv.open('w', newline='') as sf:
        writer = csv.writer(sf)
        writer.writerow([
            'iv_threshold', 'end_buffer', 'initial_capital',
            'enable_ml', 'enable_scanning', 'enable_risk_management', 'enable_news_risk', 'net_pl'
        ])
        for row in results:
            writer.writerow(row)

    print(f"Optimization complete. Summary written to {summary_csv}")


if __name__ == '__main__':
    main()
