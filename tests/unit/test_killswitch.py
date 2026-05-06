from __future__ import annotations

from botrader.risk.killswitch import KillSwitch


def test_daily_loss_kill():
    ks = KillSwitch(daily_loss_pct=0.03, max_drawdown_pct=0.50)
    ts = 1_700_000_000_000
    tripped, _ = ks.update(ts, 10_000)
    assert not tripped
    # -3% intraday
    tripped, reason = ks.update(ts + 60_000, 9_700)
    assert tripped
    assert "daily_loss" in reason


def test_max_drawdown_kill():
    ks = KillSwitch(daily_loss_pct=0.99, max_drawdown_pct=0.10)
    ts = 1_700_000_000_000
    ks.update(ts, 10_000)
    ks.update(ts + 60_000, 11_000)  # peak 11_000
    tripped, reason = ks.update(ts + 120_000, 9_900)  # drawdown 10%
    assert tripped
    assert "max_drawdown" in reason


def test_kill_persists():
    ks = KillSwitch(daily_loss_pct=0.01, max_drawdown_pct=0.50)
    ts = 1_700_000_000_000
    ks.update(ts, 10_000)
    ks.update(ts + 60_000, 9_800)  # tripped
    ts_next_day = ts + 86_400_000 * 2
    tripped, _ = ks.update(ts_next_day, 10_000)
    assert tripped, "kill switch should not auto-reset across days"
