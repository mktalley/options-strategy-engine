#!/usr/bin/env python3
import os
import argparse
from datetime import datetime
import backtrader as bt
import pandas as pd
from dotenv import load_dotenv

from strategy_selector import StrategySelector
from model_manager import ModelManager
from utils import get_iv, get_trend, get_momentum, get_next_friday


class BTOptionsStrategy(bt.Strategy):
    params = dict(iv_threshold=0.25)

    def __init__(self):
        self.selector = StrategySelector(iv_threshold=self.p.iv_threshold)
        enable_ml = os.getenv("ENABLE_ML", "false").lower() in ("true", "1", "yes")
        self.model_manager = ModelManager() if enable_ml else None

    def next(self):
        for data in self.datas:
            dt = data.datetime.date(0)
            closes = list(data.close.get(size=20))
            if len(closes) < 20:
                continue
            price = data.close[0]
            ticker = data._name

            iv = get_iv({"close_prices": closes})
            trend = get_trend({"close_prices": closes, "price": price})
            momentum = get_momentum({"close_prices": closes})
            expiration = get_next_friday(dt)

            info = {
                "ticker": ticker,
                "price": price,
                "close_prices": closes,
                "iv": iv,
                "trend": trend,
                "momentum": momentum,
                "expiration": expiration,
            }

            strat = self.selector.select(trend, iv, momentum)
            orders = strat.run(info)
            if self.model_manager:
                orders = self.model_manager.adjust_orders(orders, info)
            for o in orders:
                size = o.get("qty", 1) * 100
                if o.get("side", "").lower() == "buy":
                    self.buy(data=data, size=size, price=o.get("limit_price"))
                else:
                    self.sell(data=data, size=size, price=o.get("limit_price"))


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Backtest using Backtrader")
    parser.add_argument(
        "--csv", nargs='+', required=True,
        help="Historical CSV files with Date,Open,High,Low,Close,Volume columns"
    )
    parser.add_argument(
        "--iv-threshold", type=float, default=0.25,
        help="IV threshold for strategy selection"
    )
    parser.add_argument(
        "--cash", type=float, default=100000,
        help="Starting cash for backtest"
    )
    args = parser.parse_args()

    cerebro = bt.Cerebro()
    cerebro.addstrategy(BTOptionsStrategy, iv_threshold=args.iv_threshold)

    for csv_file in args.csv:
        ticker = os.path.splitext(os.path.basename(csv_file))[0].upper()
        df = pd.read_csv(csv_file, parse_dates=["Date"], index_col="Date")
        feed = bt.feeds.PandasData(dataname=df, name=ticker)
        cerebro.adddata(feed)

    cerebro.broker.setcash(args.cash)
    print("Starting Portfolio Value:", cerebro.broker.getvalue())
    cerebro.run()
    print("Final Portfolio Value:", cerebro.broker.getvalue())
    cerebro.plot()


if __name__ == "__main__":
    main()
