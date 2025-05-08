import os
import logging
import pytest
import requests
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
    expected_text = f"Trade executed for XYZ: orders={orders}, results={results}"
    assert captured['json']['text'] == expected_text
    assert captured['timeout'] == 5

    # Local logging should also include the message
    assert expected_text in caplog.text
