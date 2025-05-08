import os
import logging
import time
from collections import deque
import requests

class AlertManager:
    """
    Alerting module: send real-time notifications for trading events via multiple channels (Slack, Telegram, webhooks).

    Configure via environment variables:
    - ALERT_WEBHOOK_URL: Generic webhook URL (e.g., Slack incoming webhook)
    - ALERT_TELEGRAM_BOT_TOKEN: Telegram bot token
    - ALERT_TELEGRAM_CHAT_ID: Telegram chat ID to send messages to
    - ALERT_MIN_NOTIONAL: Minimum total notional value of executed trades to trigger external alerts (default 0)
    - ALERT_RATE_LIMIT_PER_MIN: Max number of external alerts per rate limit window (default 60)
    - ALERT_RATE_LIMIT_WINDOW: Rate limiting window in seconds (default 60)
    """

    def __init__(self):
        self.webhook_url = (os.getenv('ALERT_WEBHOOK_URL') or '').strip() or None
        self.tg_token = os.getenv('ALERT_TELEGRAM_BOT_TOKEN')
        self.tg_chat_id = os.getenv('ALERT_TELEGRAM_CHAT_ID')
        self.min_notional = float(os.getenv('ALERT_MIN_NOTIONAL', 0))
        self.rate_limit = int(os.getenv('ALERT_RATE_LIMIT_PER_MIN', 60))
        self.window = int(os.getenv('ALERT_RATE_LIMIT_WINDOW', 60))
        self.alert_timestamps = deque()

    def _can_send(self):
        now = time.monotonic()
        # Remove timestamps outside the rate limit window
        while self.alert_timestamps and now - self.alert_timestamps[0] > self.window:
            self.alert_timestamps.popleft()
        if len(self.alert_timestamps) < self.rate_limit:
            self.alert_timestamps.append(now)
            return True
        return False

    def send_trade_alert(self, symbol, orders, results, data):
        """
        Send an alert for executed trades based on thresholds and rate limiting.
        Always logs the alert locally.
        """
        # Compute notional for this trade
        total = 0.0
        for r in results:
            price = getattr(r, 'filled_avg_price', None)
            qty = getattr(r, 'filled_qty', None)
            try:
                if price is not None and qty is not None:
                    total += float(price) * float(qty)
            except Exception:
                continue

        msg = f"Trade executed for {symbol}: orders={orders}, results={results}, notional={total:.2f}"

        # Local log
        logging.info(f"ALERT: {msg}")

        # Check threshold
        if total < self.min_notional:
            logging.info(f"Alert suppressed: notional {total:.2f} below threshold {self.min_notional}")
            return

        # Rate limiting
        if not self._can_send():
            logging.warning(
                f"Alert rate limit reached ({self.rate_limit} per {self.window}s). Suppressing external alert."
            )
            return

        # Send to Slack webhook
        if self.webhook_url:
            try:
                payload = {"text": msg}
                requests.post(self.webhook_url, json=payload, timeout=5)
            except Exception as e:
                logging.error(f"AlertManager Slack webhook failed: {e}")

        # Send to Telegram
        if self.tg_token and self.tg_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
                payload = {"chat_id": self.tg_chat_id, "text": msg}
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                logging.error(f"AlertManager Telegram failed: {e}")
