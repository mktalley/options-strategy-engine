import os
import pytest
import smtplib
from types import SimpleNamespace
from summary_manager import SummaryManager

class DummySMTP:
    instances = []
    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.tls = False
        self.logged_in = None
        self.sent = False
        self.from_addr = None
        self.to_addrs = None
        self.msg = None
        DummySMTP.instances.append(self)
    def starttls(self):
        self.tls = True
    def login(self, username, password):
        self.logged_in = (username, password)
    def sendmail(self, from_addr, to_addrs, msg):
        self.sent = True
        self.from_addr = from_addr
        # to_addrs comes as list or comma-separated string
        if isinstance(to_addrs, str):
            self.to_addrs = to_addrs.split(',')
        else:
            self.to_addrs = to_addrs
        self.msg = msg
    def quit(self):
        pass

import logging

import pytest
import smtplib
from types import SimpleNamespace
from summary_manager import SummaryManager


@pytest.fixture(autouse=True)
def dummy_smtp(monkeypatch):
    DummySMTP.instances.clear()
    monkeypatch.setattr(smtplib, 'SMTP', DummySMTP)
    yield


def test_get_summary_no_notional():
    sm = SummaryManager()
    sm.trades = [
        {'symbol': 'A', 'strategy': 'S1', 'orders': [], 'results': [], 'data': {}},
        {'symbol': 'B', 'strategy': 'S2', 'orders': [], 'results': [], 'data': {}},
    ]
    summary = sm.get_summary()
    assert "Total trades executed: 2" in summary
    assert "- S1: 1 trades" in summary
    assert "- S2: 1 trades" in summary
    assert "Total notional traded" not in summary


def test_get_summary_with_notional():
    sm = SummaryManager()
    r1 = SimpleNamespace(filled_avg_price='10', filled_qty='2')
    r2 = SimpleNamespace(filled_avg_price='5', filled_qty='4')
    sm.trades = [
        {'symbol': 'A', 'strategy': 'S1', 'orders': [], 'results': [r1, r2], 'data': {}},
    ]
    summary = sm.get_summary()
    assert "Total trades executed: 1" in summary
    assert "- S1: 1 trades" in summary
    assert "Total notional traded: 40.00" in summary


def test_send_summary_email_success(monkeypatch):
    os.environ.update({
        'SMTP_SERVER': 'smtp.test',
        'SMTP_PORT': '25',
        'SMTP_USERNAME': 'user',
        'SMTP_PASSWORD': 'pass',
        'EMAIL_SENDER': 'sender@test',
        'EMAIL_RECIPIENTS': 'a@test,b@test'
    })
    sm = SummaryManager()
    sm.trades = [{'symbol': 'A', 'strategy': 'S', 'orders': [], 'results': [], 'data': {}}]
    sm.send_summary_email()
    # Verify SMTP instantiation and sending
    assert DummySMTP.instances, "SMTP was not instantiated"
    smtp = DummySMTP.instances[0]
    assert smtp.server == 'smtp.test'
    assert smtp.port == 25
    assert smtp.tls is True
    assert smtp.logged_in == ('user', 'pass')
    assert smtp.sent is True
    assert smtp.from_addr == 'sender@test'
    assert smtp.to_addrs == ['a@test', 'b@test']
    # trades should be cleared after sending
    assert sm.trades == []


def test_send_summary_email_no_config(monkeypatch, caplog):
    # Remove SMTP settings
    os.environ.pop('SMTP_SERVER', None)
    os.environ.pop('EMAIL_RECIPIENTS', None)
    sm = SummaryManager()
    sm.trades = [{'symbol': 'A', 'strategy': 'S', 'orders': [], 'results': [], 'data': {}}]
    caplog.set_level(logging.WARNING)
    sm.send_summary_email()
    assert "SMTP settings or recipients not configured" in caplog.text
    # trades should remain unchanged
    assert sm.trades != []
