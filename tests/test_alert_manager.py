import os
import logging
import pytest
import requests
import time
from alert_manager import AlertManager

class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise requests.HTTPError(f"Status code: {self.status_code}")


def test_send_trade_alert_no_webhook(monkeypatch, caplog):
    # Ensure no env var ALERT_WEBHOOK_URL
    monkeypatch.delenv('ALERT_WEBHOOK_URL', raising=False)
    # Monkeypatch requests.post to track calls
    called = False
    def fake_post(url, json, timeout):
        nonlocal called
        called = True
        return DummyResponse()
    monkeypatch.setattr(requests, 'post', fake_post)

    am = AlertManager()
    assert am.webhook_url is None
    caplog.set_level(logging.INFO)
    am.send_trade_alert('ABC', [{'symbol':'ABC'}], {'status':'ok'}, {'price':100})

    # requests.post should not be called when no webhook configured
    assert not called
    # Local logging always occurs
    assert 'Trade executed for ABC' in caplog.text


def test_send_trade_alert_with_webhook(monkeypatch, caplog):
    webhook_url = 'https://example.com/webhook'
    monkeypatch.setenv('ALERT_WEBHOOK_URL', webhook_url)
    # Capture post arguments
    captured = {}
    def fake_post(url, json, timeout):
        captured['url'] = url
        captured['json'] = json
        captured['timeout'] = timeout
        return DummyResponse(200)
    monkeypatch.setattr(requests, 'post', fake_post)

    orders = [{'symbol': 'XYZ', 'qty': 1}]
    results = {'id': 1}
    am = AlertManager()
    assert am.webhook_url == webhook_url

    caplog.set_level(logging.INFO)
    am.send_trade_alert('XYZ', orders, results, {})

    # Webhook should be called once with correct payload
    assert captured['url'] == webhook_url
    expected_text = f"Trade executed for XYZ: orders={orders}, results={results}, notional={0:.2f}"
    assert captured['json']['text'] == expected_text
    assert captured['timeout'] == 5

    # Local logging should also include the message


def test_threshold_suppression(monkeypatch, caplog):
    # Set minimum notional threshold higher than trade notional
    monkeypatch.setenv('ALERT_MIN_NOTIONAL', '100')
    # No external channel env
    monkeypatch.delenv('ALERT_WEBHOOK_URL', raising=False)
    monkeypatch.delenv('ALERT_TELEGRAM_BOT_TOKEN', raising=False)
    monkeypatch.delenv('ALERT_TELEGRAM_CHAT_ID', raising=False)
    # Dummy result with price*qty = 10 < threshold
    class R:
        pass
    r = R()
    r.filled_avg_price = 10
    r.filled_qty = 1
    called = False
    def fake_post(url, json, timeout):
        nonlocal called
        called = True
        return DummyResponse()
    monkeypatch.setattr(requests, 'post', fake_post)
    am = AlertManager()
    caplog.set_level(logging.INFO)
    am.send_trade_alert('TEST', [], [r], {})
    # No external post should be called due to threshold
    assert not called
    assert 'suppressed' in caplog.text.lower()

def test_send_trade_alert_telegram(monkeypatch, caplog):
    token = '123:ABC'
    chat_id = '999'
    monkeypatch.setenv('ALERT_TELEGRAM_BOT_TOKEN', token)
    monkeypatch.setenv('ALERT_TELEGRAM_CHAT_ID', chat_id)
    monkeypatch.delenv('ALERT_WEBHOOK_URL', raising=False)
    # Dummy result with price*qty = 12 > default threshold 0
    class R:
        pass
    r = R()
    r.filled_avg_price = 2
    r.filled_qty = 6
    captured = []
    def fake_post(url, json, timeout):
        captured.append((url, json, timeout))
        return DummyResponse()
    monkeypatch.setattr(requests, 'post', fake_post)
    am = AlertManager()
    caplog.set_level(logging.INFO)
    am.send_trade_alert('TELE', [], [r], {})
    # Telegram should be called once with correct payload
    assert len(captured) == 1
    url, json_payload, timeout = captured[0]
    assert url == f"https://api.telegram.org/bot{token}/sendMessage"
    assert json_payload['chat_id'] == chat_id
    assert 'Trade executed for TELE' in json_payload['text']

def test_rate_limit_enforcement(monkeypatch, caplog):
    monkeypatch.setenv('ALERT_RATE_LIMIT_PER_MIN', '2')
    monkeypatch.setenv('ALERT_RATE_LIMIT_WINDOW', '1000')
    monkeypatch.setenv('ALERT_WEBHOOK_URL', 'https://example.com')
    # Dummy result with price*qty = 1
    class R:
        pass
    r = R()
    r.filled_avg_price = 1
    r.filled_qty = 1
    # Simulate time progression
    times = [1, 2, 3]
    def fake_time():
        return times.pop(0)
    monkeypatch.setattr(time, 'monotonic', fake_time)
    calls = []
    def fake_post(url, json, timeout):
        calls.append(json['text'])
        return DummyResponse()
    monkeypatch.setattr(requests, 'post', fake_post)
    am = AlertManager()
    caplog.set_level(logging.WARNING)
    am.send_trade_alert('A', [], [r], {})
    am.send_trade_alert('B', [], [r], {})
    am.send_trade_alert('C', [], [r], {})
    # Only first two should have sent external alerts
    assert len(calls) == 2
    assert 'rate limit' in caplog.text.lower()
    # Ensure rate limit warning message is logged
    assert 'suppressing external alert' in caplog.text.lower()
    assert calls[0].startswith("Trade executed for A")
    assert calls[1].startswith("Trade executed for B")
