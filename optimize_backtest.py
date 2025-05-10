#!/usr/bin/env python3
"""
Script to perform a grid search over backtest CLI flag combinations and summarize net P/L for each.
Usage:
    python optimize_backtest.py --tickers SPY,AAPL --start 2025-01-01 --end 2025-05-07
"""
import subprocess
import sys
import os
import itertools
import argparse
import csv
from pathlib import Path
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Optimize backtest flag combinations")
    parser.add_argument('--tickers', required=True, help='Comma-separated tickers')
    parser.add_argument('--start', required=True, help='Backtest start date YYYY-MM-DD')
    parser.add_argument('--end', required=True, help='Backtest end date YYYY-MM-DD')
    parser.add_argument('--output-dir', default=os.getenv('OPTIMIZE_OUTPUT_DIR', 'outputs/optimize/results'), help='Base dir for all runs [env: OPTIMIZE_OUTPUT_DIR]')
    parser.add_argument('--iv-thresholds', nargs='+', type=float,
                        default=[0.2, 0.25, 0.3], help='List of IV thresholds to test')
    parser.add_argument('--end-buffer-minutes', nargs='+', type=int,
                        default=[5, 10, 15], help='List of end-buffer minutes')
    parser.add_argument('--initial-capitals', nargs='+', type=float,
                        default=[100000.0], help='List of starting capitals')
    # NOTE: scanning toggle will be set per-combo and not via global flag
    # toggles for ML and scanning will be handled per-combo (no global CLI flags)
    args = parser.parse_args()

    # Build grid over iv, end-buffer, capital, ML toggle, scanning toggle, risk-management toggle, and news-risk toggle
    ml_flags = [False, True]
    scan_flags = [False, True]
    risk_flags = [False, True]
    news_flags = [False, True]
    combos = list(itertools.product(
        args.iv_thresholds,
        args.end_buffer_minutes,
        args.initial_capitals,
        ml_flags,
        scan_flags,
        risk_flags,
        news_flags
    ))
    base_output = Path(args.output_dir)
    base_output.mkdir(parents=True, exist_ok=True)
    summary_csv = base_output / 'summary.csv'

    with summary_csv.open('w', newline='') as sf:
        writer = csv.writer(sf)
        writer.writerow(['iv_threshold', 'end_buffer', 'initial_capital', 'enable_ml', 'enable_scanning', 'enable_risk_management', 'enable_news_risk', 'net_pl'])
        for iv, eb, ic, enable_ml, enable_scan, enable_risk, enable_news in combos:
            combo_dir = base_output / f"iv{iv}_eb{eb}_ic{int(ic)}"
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
            # toggle scanning on/off based on current combo
            if enable_scan:
                cmd.append('--enable-scanning')
            else:
                cmd.append('--disable-scanning')
            # toggle ML on/off based on current combo
            if enable_ml:
                cmd.append('--enable-ml')
            else:
                cmd.append('--disable-ml')
            # toggle risk management on/off based on current combo
            if enable_risk:
                cmd.append('--enable-risk-management')
            else:
                cmd.append('--disable-risk-management')
            # toggle news risk on/off based on current combo
            if enable_news:
                cmd.append('--enable-news-risk')
            else:
                cmd.append('--disable-news-risk')

            print(f"Running combo: IV={iv}, EndBuffer={eb}, Capital={ic}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  Error for combo {iv, eb, ic}: {result.stderr.strip()}")
                net_pl = None
            else:
                # locate results CSV under results_csv/ folder
                run_id = f"{args.start}_to_{args.end}_{args.tickers.replace(',', '_')}"
                results_path = combo_dir / run_id / 'results_csv'
                csv_files = list(results_path.glob('*.csv'))
                if csv_files:
                    df = pd.read_csv(csv_files[0])
                    net_pl = df['pl'].sum()
                else:
                    net_pl = 0.0
            writer.writerow([iv, eb, ic, enable_ml, enable_scan, enable_risk, enable_news, net_pl])
    print(f"Optimization complete. Summary written to {summary_csv}")


if __name__ == '__main__':
    main()
