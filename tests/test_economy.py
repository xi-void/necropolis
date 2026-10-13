import copy
import json
import unittest

from necropolis.economy import Economy, event_flows, gini, worker_status
from necropolis.observer import Observer
from necropolis.simulation import Config, World, replay


class EconomyTests(unittest.TestCase):
    def test_measurements_do_not_change_rules_events_or_rng(self):
        a, b = World(Config(seed=47)), World(Config(seed=47))
        b.economy.consume = lambda event: None
        for _ in range(72):
            a.step()
            b.step()
        sa, sb = a.state(), b.state()
        sa.pop("economy")
        sb.pop("economy")
        self.assertEqual(sa, sb)
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.rng.getstate(), b.rng.getstate())

    def test_internal_transfers_are_not_production(self):
        self.assertEqual(event_flows(dict(kind="gather", amount=1)), {})
        self.assertEqual(event_flows(dict(kind="ore_delivered", amount=4)), {})
        self.assertEqual(event_flows(dict(kind="trade")), {"trades": 1})
        self.assertEqual(event_flows(dict(kind="ore_export", ore=1, food_imported=2)),
                         {"ore_exported": 1, "food_imported": 2})

    def test_window_expiry_and_partial_day_normalization(self):
        w = World(Config(mine_count=0, grave_count=0, necromancy=False))
        w.economy = Economy()
        w.tick = 1
        w.economy.consume(dict(tick=1, kind="grow", amount=2))
        self.assertEqual(w.economy.current(w)["rates"]["food_produced"], 48)
        w.tick = 25
        w.economy.advance(25)
        current = w.economy.current(w)
        self.assertEqual(current["flows"].get("food_produced", 0), 0)
        self.assertEqual(current["totals"]["food_produced"], 2)

    def test_history_balances_and_persists_after_extinction(self):
        w = World(Config(seed=47, patches=0, necromancy=False, mine_count=0, grave_count=0))
        for _ in range(96):
            w.step()
        self.assertEqual([r["tick"] for r in w.economy.history], [0, 24, 48, 72, 96])
        self.assertEqual(w.economy.history[-1]["living"], 0)
        for row in w.economy.history:
            total = row["totals"]
            self.assertEqual(row["food"], w.economy.history[0]["food"]
                             + total.get("food_produced", 0) + total.get("food_imported", 0)
                             - total.get("food_consumed", 0))

    def test_gini_has_defined_zero_population_and_equal_wealth_behavior(self):
        self.assertEqual(gini([]), 0)
        self.assertEqual(gini([0, 0]), 0)
        self.assertEqual(gini([12] * 20), 0)
        self.assertEqual(gini([0, 24]), .5)

    def test_serialized_history_replay_and_tamper_detection(self):
        w = World(Config(seed=47))
        for _ in range(48):
            w.step()
        record = json.loads(json.dumps(w.record()))
        self.assertEqual(replay(record).economy.history, w.economy.history)
        record["economy_history"][0]["food"] += 1
        with self.assertRaises(ValueError):
            replay(record)

    def test_adapter_history_is_detached_and_never_duplicated(self):
        w = World()
        o = Observer(w)
        for _ in range(24):
            o.step()
        original = copy.deepcopy(w.economy.history)
        o.economy_history[0]["food"] = -1
        for _ in range(3):
            o.refresh()
        self.assertEqual(len(o.economy_history), 2)
        self.assertEqual(w.economy.history, original)

    def test_worker_reports_blocked_delivery_and_maintenance(self):
        keeper = dict(alive=True, x=0, y=0, ore=8, mana=0)
        worker = dict(keeper_id=1, x=0, y=0, ore=4, active=True, mine_id=None)
        self.assertIn("storage full", worker_status(worker, {1: keeper}, {}, 1))
        worker["active"] = False
        self.assertIn("lacks mana", worker_status(worker, {1: keeper}, {}, 1))
        keeper["alive"] = False
        self.assertIn("deceased", worker_status(worker, {1: keeper}, {}, 1))


if __name__ == "__main__":
    unittest.main()
