import asyncio
import pytest

import main

class DummyScheduler:
    def __init__(self, timezone=None):
        self.timezone = timezone
        self.jobs = []
    def add_job(self, func, trigger, args=None, day_of_week=None, hour=None, minute=None):
        self.jobs.append({
            'func': func,
            'trigger': trigger,
            'args': args,
            'day_of_week': day_of_week,
            'hour': hour,
            'minute': minute
        })
    def start(self):
        pass

@pytest.mark.asyncio
async def test_event_loop_schedules_summary(monkeypatch):
    
    # Holder for scheduler instance
    scheduler_holder = {}
    # Fake AsyncIOScheduler to capture the instance
    def fake_scheduler(timezone=None):
        sched = DummyScheduler(timezone=timezone)
        scheduler_holder['sched'] = sched
        return sched
    monkeypatch.setattr(main, 'AsyncIOScheduler', fake_scheduler)
    # Monkeypatch stream_listener to no-op to exit event_loop promptly
    monkeypatch.setattr(main, 'stream_listener', lambda *args, **kwargs: asyncio.sleep(0))

    # Run event_loop with dummy parameters
    selector = object()
    executor = object()
    api_key = 'a'
    secret_key = 'b'
    base_url = 'c'
    tickers = []

    await main.event_loop(selector, executor, api_key, secret_key, base_url, tickers)

    sched = scheduler_holder.get('sched')
    assert sched is not None, "Scheduler was not instantiated"
    # Find summary email job among scheduled jobs
    funcs = [job['func'] for job in sched.jobs]
    assert main.summary_manager.send_summary_email in funcs, \
        "Summary email job was not scheduled"
