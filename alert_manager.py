import os
import logging
import requests

class AlertManager:
    """
    Alerting module: send real-time notifications for trading events via webhook.
    Configure via environment variable:
    - ALERT_WEBHOOK_URL: Generic webhook URL (e.g., Slack incoming webhook)
    """

    def __init__(self):
        self.webhook_url = os.getenv('ALERT_WEBHOOK_URL')

    def send_trade_alert(self, symbol, orders, results, data):
        """
        Send an alert for executed trades.
        If ALERT_WEBHOOK_URL is set, POST a JSON payload to the webhook.
        Always logs the alert.

        Payload JSON includes:
        - text: formatted message string
        """
        # Build message text
        msg = f"Trade executed for {symbol}: orders={orders}, results={results}"
        # Send to webhook if configured
        if self.webhook_url:
            try:
                payload = {"text": msg}
                requests.post(self.webhook_url, json=payload, timeout=5)
            except Exception as e:
                logging.error(f"AlertManager failed to send alert: {e}")
        # Always log the alert locally
        logging.info(f"ALERT: {msg}")


