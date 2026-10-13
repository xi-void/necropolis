import json
import unittest

from necropolis.simulation import Config, World, replay


class OreTests(unittest.TestCase):
    def world(self):
        return World(Config(seed=47, mine_count=1))

    def test_living_extraction_depletes_finite_deposit(self):
        w = self.world()
        miner = next(c for c in w.citizens if c.occupation == "miner")
        mine = w.mines[0]
        miner.x, miner.y = mine.x, mine.y
        mine.remaining = 1
        w.perceive(miner)
        w.act(miner)
        self.assertEqual((mine.remaining, miner.ore), (0, 1))
        with self.assertRaises(ValueError):
            w.extract(miner, mine, miner.id)
        miner.sleeping = True
        mine.remaining = 1
        with self.assertRaises(ValueError):
            w.extract(miner, mine, miner.id)

    def test_local_ore_trade_and_external_market_are_separate_flows(self):
        w = self.world()
        seller = next(c for c in w.citizens if c.occupation == "miner")
        buyer = next(c for c in w.citizens if c.occupation == "merchant")
        seller.x = buyer.x = seller.y = buyer.y = 0
        seller.ore, buyer.food = 1, 0
        w.trade_ore(buyer, seller)
        self.assertEqual((seller.money, buyer.money), (13, 11))
        self.assertEqual((seller.ore, buyer.ore), (0, 1))
        w.export_ore(buyer)
        self.assertEqual((buyer.ore, buyer.food), (0, 2))
        self.assertEqual((w.total_exports, w.total_imports), (1, 2))
        self.assertEqual(sum(c.money for c in w.citizens), 240)
        self.assertEqual(w.events[-1]["kind"], "ore_export")

    def test_quota_storage_and_locality(self):
        w = self.world()
        buyer = next(c for c in w.citizens if c.occupation == "merchant")
        seller = w.citizens[0]
        buyer.x = buyer.y = 0
        seller.x, seller.y, seller.ore = 20, 10, 1
        with self.assertRaises(ValueError):
            w.trade_ore(buyer, seller)
        buyer.ore, buyer.food = 1, buyer.capacity
        with self.assertRaises(ValueError):
            w.export_ore(buyer)
        buyer.food = 0
        w.exports_today = w.config.daily_ore_exports
        with self.assertRaises(ValueError):
            w.export_ore(buyer)
        w.tick = 23
        buyer.sleeping = True
        w.step()
        self.assertEqual(w.exports_today, 0)

    def test_inactive_workers_do_not_mine_and_deliver_physically(self):
        w = self.world()
        c = next(c for c in w.citizens if c.occupation == "necromancer")
        body = w.corpses[0]
        c.x, c.y = body.x, body.y
        w.exhume(c, body)
        w.animate(c, body)
        u, mine = w.undead[0], w.mines[0]
        u.x, u.y, u.mine_id = mine.x, mine.y, mine.id
        w.tick = 1
        u.active = False
        w.work_undead()
        self.assertEqual(u.ore, 0)
        u.active = True
        w.work_undead()
        self.assertEqual(u.ore, 1)
        self.assertEqual(c.ore, 0)
        u.ore = 4
        c.x, c.y = u.x, u.y
        w.work_undead()
        self.assertEqual((u.ore, c.ore), (0, 4))

    def test_dropped_ore_preserved_on_death_and_worker_removal(self):
        w = self.world()
        c = next(c for c in w.citizens if c.occupation == "necromancer")
        body = w.corpses[0]
        c.x, c.y = body.x, body.y
        w.exhume(c, body)
        w.animate(c, body)
        c.ore = 3
        u = w.undead[0]
        u.ore, u.integrity = 2, 1
        w.die(c, "starvation")
        w.maintain_undead()
        self.assertEqual(sum(w.ground_ore.values()), 5)
        self.assertEqual(c.ore, 0)
        self.assertEqual(w.undead, [])

    def test_accounting_and_replay_across_seeds(self):
        for seed in (1, 47, 99):
            w = World(Config(seed=seed))
            food_initial = sum(w.food.values()) + sum(c.food for c in w.citizens)
            for _ in range(240):
                w.step()
            mined = sum(m.initial - m.remaining for m in w.mines)
            ore_stock = sum(c.ore for c in w.citizens) + sum(u.ore for u in w.undead) + sum(w.ground_ore.values())
            self.assertEqual(mined, ore_stock + w.total_exports)
            grown = sum(e.get("amount", 0) for e in w.events if e["kind"] in ("grow", "produce"))
            eaten = sum(e["kind"] == "eat" for e in w.events)
            self.assertEqual(food_initial + grown + w.total_imports - eaten,
                             sum(w.food.values()) + sum(c.food for c in w.citizens))
            self.assertEqual(sum(c.money for c in w.citizens), 240)
            self.assertTrue(all(c.money >= 0 and 0 <= c.ore <= 8 for c in w.citizens))
            self.assertEqual(replay(json.loads(json.dumps(w.record()))).state(), w.state())

    def test_unseen_mines_do_not_enter_knowledge(self):
        w = self.world()
        c, mine = w.citizens[0], w.mines[0]
        c.x, c.y = (mine.x + 12) % w.config.width, mine.y
        w.perceive(c)
        self.assertEqual(c.mine_memory, [])


if __name__ == "__main__":
    unittest.main()
