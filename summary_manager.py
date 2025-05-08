import os
import smtplib
import logging
from datetime import date
from email.mime.text import MIMEText

class SummaryManager:
    """
    Collects executed trade details and sends a daily summary email.
    Environment variables:
      SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
      EMAIL_SENDER (optional), EMAIL_RECIPIENTS (comma-separated)
    """
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_sender = os.getenv('EMAIL_SENDER', self.smtp_username)
        recipients = os.getenv('EMAIL_RECIPIENTS', '')
        self.email_recipients = [r.strip() for r in recipients.split(',') if r.strip()]
        self.trades = []

    def record_trade(self, symbol, strategy_name, orders, results, data):
        """
        Record a trade for the daily summary.
        """
        self.trades.append({
            'symbol': symbol,
            'strategy': strategy_name,
            'orders': orders,
            'results': results,
            'data': data
        })

    def get_summary(self):
        total_trades = len(self.trades)
        by_strategy = {}
        for t in self.trades:
            name = t['strategy']
            by_strategy[name] = by_strategy.get(name, 0) + 1

        lines = [f"Daily Trade Summary for {date.today()}",
                 f"Total trades executed: {total_trades}",
                 ""]
        for strat, count in by_strategy.items():
            lines.append(f"- {strat}: {count} trades")
        # Calculate total notional executed if available
        total_notional = 0.0
        for t in self.trades:
            for r in t.get('results', []):
                filled_price = getattr(r, 'filled_avg_price', None)
                filled_qty = getattr(r, 'filled_qty', None)
                try:
                    price = float(filled_price)
                    qty = float(filled_qty)
                    total_notional += price * qty
                except Exception:
                    continue
        if total_notional:
            lines.append(f"Total notional traded: {total_notional:.2f}")
        return "\n".join(lines)


    def send_summary_email(self):
        summary = self.get_summary()
        if not self.smtp_server or not self.email_recipients:
            logging.warning("SMTP settings or recipients not configured; skipping summary email")
            return
        msg = MIMEText(summary)
        msg['Subject'] = f"Daily Trade Summary {date.today()}"
        msg['From'] = self.email_sender
        msg['To'] = ",".join(self.email_recipients)
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.email_sender, self.email_recipients, msg.as_string())
            server.quit()
            logging.info("Daily summary email sent successfully")
            # Clear recorded trades after sending summary
            self.trades.clear()
        except Exception as e:
            logging.error(f"Failed to send summary email: {e}")
