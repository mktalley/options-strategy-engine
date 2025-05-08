#!/usr/bin/env python3
"""
Simulate an equity curve from backtest_results.csv for a given calendar year.
Usage:
    python simulate_equity.py --start 2024-01-01 --end 2025-01-01 --initial-capital 100000
"""
import argparse
import pandas as pd
import matplotlib.pyplot as plt

def simulate_equity(csv_path, start_date, end_date, initial_capital):
    # Load detailed trade results
    df = pd.read_csv(csv_path, parse_dates=["entry_date", "expiration"])

    # Filter by entry_date window
    mask = (df["entry_date"] >= pd.to_datetime(start_date)) & \
           (df["entry_date"] <  pd.to_datetime(end_date))
    df = df.loc[mask].copy()
    if df.empty:
        print(f"No trades found between {start_date} and {end_date}.")
        return

    # Use expiration date as P/L realization date
    df["pl_date"] = pd.to_datetime(df["expiration"]).dt.date

    # Ensure P/L is numeric; missing => 0
    df["pl"] = pd.to_numeric(df["pl"], errors="coerce").fillna(0.0)

    # Sum daily P/L
    daily_pl = df.groupby("pl_date")["pl"].sum().sort_index()

    # Build equity series
    equity = daily_pl.cumsum().add(initial_capital)
    equity.index = pd.to_datetime(equity.index)

    # Print summary
    start_eq = initial_capital
    end_eq = equity.iloc[-1]
    net_pl = end_eq - start_eq
    ret = (net_pl / start_eq) * 100
    print(f"Start capital: $ {start_eq:,.2f}")
    print(f"End capital:   $ {end_eq:,.2f}")
    print(f"Net P/L:       $ {net_pl:,.2f}")
    print(f"Return:         {ret:.2f}%")

    # Plot
    plt.figure(figsize=(10,5))
    plt.plot(equity.index, equity.values, lw=2)
    plt.title(f"Equity Curve {start_date} to {end_date}")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.grid(True)
    out_png = f"equity_curve_{start_date}_to_{end_date}.png"
    plt.tight_layout()
    plt.savefig(out_png)
    print(f"Equity curve saved to {out_png}")

if __name__ == '__main__':
    p = argparse.ArgumentParser(description="Simulate portfolio equity from a backtest CSV.")
    p.add_argument('--csv', default='backtest_results.csv', help='Path to backtest_results.csv')
    p.add_argument('--start', required=True, help='Start date YYYY-MM-DD')
    p.add_argument('--end',   required=True, help='End date YYYY-MM-DD')
    p.add_argument('--initial-capital', type=float, default=100000.0, help='Starting capital')
    args = p.parse_args()
    simulate_equity(args.csv, args.start, args.end, args.initial_capital)
