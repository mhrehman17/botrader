from __future__ import annotations

from botrader.risk.sizing import ContractSpec, size_position


def test_basic_sizing():
    # equity 10_000, 0.5% risk, SL distance 50 -> qty = 50/50 = 1
    spec = ContractSpec(qty_step=0.001, min_qty=0.001, contract_size=1.0)
    qty = size_position(equity=10_000, risk_pct=0.005, entry=1000, stop_loss=950, spec=spec)
    assert qty == 1.0


def test_zero_when_below_min():
    spec = ContractSpec(qty_step=0.1, min_qty=1.0)
    qty = size_position(equity=10, risk_pct=0.005, entry=1000, stop_loss=995, spec=spec)
    assert qty == 0.0


def test_capped_by_leverage():
    # Without cap: risk 100$ / 1$ stop = 100 qty * 1000 entry = 100_000 notional
    # 10x leverage cap on 10_000 equity = 100_000 notional max -> still 100 qty
    # but with 5x, it's 50_000 -> 50 qty
    spec = ContractSpec(qty_step=0.001, min_qty=0.001)
    qty = size_position(equity=10_000, risk_pct=0.01, entry=1000, stop_loss=999,
                        spec=spec, max_leverage=5)
    assert qty == 50.0
