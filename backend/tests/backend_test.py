"""Backend API tests for Upstox Regime-Adaptive Trading System."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://regime-adaptive-bot.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- System/Root ----------
class TestSystem:
    def test_root(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        d = r.json()
        assert d["service"] == "Upstox Regime-Adaptive Trading"
        assert "version" in d
        assert "time" in d

    def test_status(self, client):
        r = client.get(f"{API}/status")
        assert r.status_code == 200
        d = r.json()
        for k in ["paper_mode", "capital", "max_daily_loss", "target_gross",
                  "signal_threshold", "upstox", "telegram", "today", "server_time"]:
            assert k in d, f"Missing key {k}"
        assert isinstance(d["paper_mode"], bool)
        today = d["today"]
        for k in ["gross_pnl", "total_charges", "net_pnl", "num_trades", "wins", "losses"]:
            assert k in today


# ---------- Settings ----------
class TestSettings:
    def test_get_settings_defaults(self, client):
        r = client.get(f"{API}/settings")
        assert r.status_code == 200
        d = r.json()
        assert d["capital"] == 600000
        assert isinstance(d["watchlist"], list)
        assert len(d["watchlist"]) == 10
        assert isinstance(d["weights"], dict)
        total_w = sum(d["weights"].values())
        assert 0.98 <= total_w <= 1.02, f"weights sum={total_w}"

    def test_update_settings_persists(self, client):
        # Update
        payload = {"target_gross": 4600, "signal_threshold": 0.70}
        r = client.put(f"{API}/settings", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["updated"]["target_gross"] == 4600

        # Verify persistence
        r2 = client.get(f"{API}/settings")
        d2 = r2.json()
        assert d2["target_gross"] == 4600
        assert d2["signal_threshold"] == 0.70

        # Reset
        client.put(f"{API}/settings", json={"target_gross": 4500, "signal_threshold": 0.68})

    def test_toggle_paper_mode(self, client):
        r = client.put(f"{API}/settings", json={"paper_mode": False})
        assert r.status_code == 200
        r2 = client.get(f"{API}/settings")
        assert r2.json()["paper_mode"] is False
        client.put(f"{API}/settings", json={"paper_mode": True})


# ---------- Regime ----------
class TestRegime:
    def test_regime_now(self, client):
        r = client.get(f"{API}/regime")
        assert r.status_code == 200
        d = r.json()
        assert d.get("regime") in ["Bull", "Sideways", "Bear", "Unknown"]
        assert "confidence" in d
        assert "probabilities" in d

    def test_regime_timeline(self, client):
        r = client.get(f"{API}/regime/timeline?days=30")
        assert r.status_code == 200
        tl = r.json().get("timeline", [])
        assert isinstance(tl, list)
        if tl:
            assert "date" in tl[0] and "regime" in tl[0]


# ---------- Morning brief / EOD / Signals ----------
class TestMarketFlows:
    def test_morning_brief(self, client):
        r = client.get(f"{API}/morning-brief")
        assert r.status_code == 200
        d = r.json()
        for k in ["timestamp", "regime", "global_cues", "top_signals", "target_gross"]:
            assert k in d
        assert d["target_gross"] == 4500
        for c in ["sp500", "nifty", "india_vix", "crude", "usdinr"]:
            assert c in d["global_cues"], f"Missing cue {c}"
        assert isinstance(d["top_signals"], list)

    def test_eod_summary(self, client):
        r = client.get(f"{API}/eod-summary")
        assert r.status_code == 200
        d = r.json()
        for k in ["num_trades", "gross_pnl", "total_charges", "net_pnl",
                  "wins", "losses", "win_rate", "trades"]:
            assert k in d

    def test_signals(self, client):
        r = client.get(f"{API}/signals")
        assert r.status_code == 200
        d = r.json()
        sigs = d["signals"]
        assert len(sigs) == 10
        first = sigs[0]
        for k in ["composite", "action", "meets_threshold", "layers", "price", "change_pct"]:
            assert k in first
        assert first["action"] in ["BUY", "HOLD", "SELL"]
        for layer in ["technical", "sentiment", "fii_flow", "gex", "global_cue"]:
            assert layer in first["layers"], f"Missing layer {layer}"


# ---------- Charges / Risk ----------
class TestRiskAndCharges:
    def test_charges_today(self, client):
        r = client.get(f"{API}/charges/today")
        assert r.status_code == 200
        d = r.json()
        for k in ["brokerage", "stt", "exchange_txn", "sebi", "stamp", "gst", "total"]:
            assert k in d, f"Missing charge {k}"

    def test_risk_monitor(self, client):
        r = client.get(f"{API}/risk")
        assert r.status_code == 200
        d = r.json()
        for k in ["capital", "daily_loss_cap", "loss_used", "loss_used_pct",
                  "open_positions", "max_positions", "vix", "regime",
                  "trades_allowed", "block_reason"]:
            assert k in d
        if d["regime"] == "Bear":
            assert d["trades_allowed"] is False
            assert d["block_reason"] is not None


# ---------- Paper trading ----------
class TestPaperTrading:
    def test_seed_demo(self, client):
        r = client.post(f"{API}/seed-demo")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_trades_list_after_seed(self, client):
        r = client.get(f"{API}/trades?limit=10")
        assert r.status_code == 200
        trades = r.json()["trades"]
        assert len(trades) >= 1
        t0 = trades[0]
        assert "charges" in t0
        assert "gross_pnl" in t0
        assert "net_pnl" in t0

    def test_positions_initially_empty(self, client):
        # after seed, positions got cleared
        r = client.get(f"{API}/positions")
        assert r.status_code == 200
        assert "positions" in r.json()

    def test_open_and_close_position(self, client):
        # open
        r = client.post(f"{API}/paper/open", json={"symbol": "RELIANCE"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "position" in d
        assert "sizing" in d
        assert "signal" in d
        pos = d["position"]
        pos_id = pos["id"]
        assert pos["symbol"] == "RELIANCE"
        assert pos["qty"] > 0

        # GET verify
        r2 = client.get(f"{API}/positions")
        ids = [p["id"] for p in r2.json()["positions"]]
        assert pos_id in ids

        # close
        r3 = client.post(f"{API}/paper/close/{pos_id}")
        assert r3.status_code == 200
        tr = r3.json()["trade"]
        assert tr["symbol"] == "RELIANCE"
        assert "charges" in tr
        assert "gross_pnl" in tr
        assert "net_pnl" in tr

        # verify removed
        r4 = client.get(f"{API}/positions")
        ids2 = [p["id"] for p in r4.json()["positions"]]
        assert pos_id not in ids2

    def test_close_all(self, client):
        # open two
        client.post(f"{API}/paper/open", json={"symbol": "TCS"})
        client.post(f"{API}/paper/open", json={"symbol": "INFY"})
        r = client.post(f"{API}/paper/close-all")
        assert r.status_code == 200
        d = r.json()
        assert d["count"] >= 1
        # verify none open
        r2 = client.get(f"{API}/positions")
        assert len(r2.json()["positions"]) == 0


# ---------- Charges math ----------
class TestChargesMath:
    def test_charges_formula(self):
        from trading.charges import calc_charges
        buy, sell, qty = 100.0, 102.0, 100
        c = calc_charges(buy, sell, qty)
        turnover_buy = buy * qty
        turnover_sell = sell * qty
        total = turnover_buy + turnover_sell
        expected_brokerage = (min(20, turnover_buy * 0.0005) +
                              min(20, turnover_sell * 0.0005))
        expected_stt = turnover_sell * 0.00025
        expected_exch = total * 0.0000297
        expected_sebi = total * 10 / 1e7
        expected_stamp = turnover_buy * 0.00003
        expected_gst = 0.18 * (expected_brokerage + expected_exch + expected_sebi)
        assert abs(c.brokerage - expected_brokerage) < 0.01
        assert abs(c.stt - expected_stt) < 0.01
        assert abs(c.exchange_txn - expected_exch) < 0.01
        assert abs(c.sebi - expected_sebi) < 0.01
        assert abs(c.stamp - expected_stamp) < 0.01
        assert abs(c.gst - expected_gst) < 0.01


# ---------- Upstox ----------
class TestUpstox:
    def test_upstox_status(self, client):
        r = client.get(f"{API}/upstox/status")
        assert r.status_code == 200
        d = r.json()
        for k in ["configured", "has_token", "state"]:
            assert k in d

    def test_upstox_configure(self, client):
        r = client.post(f"{API}/upstox/configure", json={
            "api_key": "TEST_key", "api_secret": "TEST_secret"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ---------- Telegram ----------
class TestTelegram:
    def test_telegram_status(self, client):
        r = client.get(f"{API}/telegram/status")
        assert r.status_code == 200
        d = r.json()
        assert "configured" in d
        assert "recent" in d

    def test_telegram_configure(self, client):
        r = client.post(f"{API}/telegram/configure", json={
            "bot_token": "123:ABCDEF_fake_token", "chat_id": "12345"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_telegram_send_test_invalid(self, client):
        r = client.post(f"{API}/telegram/send-test")
        assert r.status_code == 200
        d = r.json()
        # should return ok:false since token is fake
        assert d.get("ok") is False


# ---------- Backtest ----------
class TestBacktest:
    def test_backtest_latest_initial(self, client):
        r = client.get(f"{API}/backtest/latest")
        assert r.status_code == 200
        # Either {none: true} or a result dict

    @pytest.mark.timeout(180)
    def test_backtest_run(self, client):
        r = client.post(f"{API}/backtest/run", json={"period": "2y"}, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["total_trades", "win_rate", "gross_pnl", "total_charges",
                  "net_pnl", "sharpe", "max_drawdown", "target_hit_rate",
                  "monthly", "equity_curve", "sample_trades"]:
            assert k in d, f"Missing backtest key {k}"
        assert isinstance(d["monthly"], list)
        assert isinstance(d["equity_curve"], list)

    def test_backtest_latest_after_run(self, client):
        r = client.get(f"{API}/backtest/latest")
        assert r.status_code == 200
        d = r.json()
        # after run, should have total_trades
        assert d.get("none") is not True
