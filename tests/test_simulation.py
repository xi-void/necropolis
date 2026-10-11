import copy
import unittest

from necropolis.simulation import Config, World, replay


class SimulationTests(unittest.TestCase):
    def test_determinism_and_replay(self):
        a, b = World(Config(seed=47)), World(Config(seed=47))
        for _ in range(240):
            a.step()
            b.step()
        self.assertEqual(a.record(), b.record())
        self.assertEqual(replay(a.record()).state(), a.state())
        damaged = copy.deepcopy(a.record())
        damaged["events"][0]["kind"] = "invented"
        with self.assertRaises(ValueError):
            replay(damaged)

    def test_resource_accounting_across_seeds(self):
        for seed in range(10):
            world = World(Config(seed=seed))
            initial = sum(world.food.values()) + sum(c.food for c in world.citizens)
            for _ in range(240):
                world.step()
            growth = sum(e.get("amount", 0) for e in world.events if e["kind"] in ("grow", "produce"))
            consumed = sum(e["kind"] == "eat" for e in world.events)
            remaining = sum(world.food.values()) + sum(c.food for c in world.citizens)
            self.assertEqual(initial + growth - consumed, remaining)
            self.assertTrue(all(v >= 0 for v in world.food.values()))
            self.assertEqual(sum(c.money for c in world.citizens), 12 * len(world.citizens))
            self.assertTrue(all(c.money >= 0 and 0 <= c.food <= c.capacity for c in world.citizens))

    def test_local_trade_transfers_food_and_money(self):
        world = World(Config(citizens=2, patches=0))
        seller, buyer = world.citizens
        seller.x = buyer.x = seller.y = buyer.y = 0
        seller.food, buyer.food = 5, 0
        world.step()
        self.assertEqual((seller.food, buyer.food), (4, 1))
        self.assertEqual((seller.money, buyer.money), (13, 11))
        self.assertEqual(world.events[-1]["kind"], "trade")
        self.assertEqual(world.events[-1]["seller"], seller.id)

    def test_farmer_produces_only_on_patch(self):
        world = World(Config(citizens=1, patches=1))
        farmer = world.citizens[0]
        farmer.x, farmer.y = next(iter(world.patches))
        world.step()
        self.assertEqual(farmer.food, 3)
        self.assertEqual(world.events[-1]["kind"], "produce")
        empty = World(Config(citizens=1, patches=0))
        empty.step()
        self.assertEqual(empty.citizens[0].food, 2)
        self.assertFalse(any(e["kind"] == "produce" for e in empty.events))

    def test_trade_requires_local_affordable_surplus(self):
        world = World(Config(citizens=2, patches=0))
        seller, buyer = world.citizens
        seller.food, buyer.food = 5, 0
        seller.x = seller.y = 0
        buyer.x, buyer.y = 20, 10
        self.assertEqual(world.sellers(buyer), [])
        buyer.x = buyer.y = 0
        buyer.money = 0
        self.assertEqual(world.sellers(buyer), [])
        buyer.money = 12
        seller.food = 2
        self.assertEqual(world.sellers(buyer), [])

    def test_dropped_food_does_not_create_renewable_patch(self):
        world = World(Config(citizens=1, patches=0))
        world.citizens[0].food = 0
        for _ in range(72):
            world.step()
        self.assertEqual(sum(world.food.values()), 0)

    def test_unseen_food_does_not_change_decision(self):
        a = World(Config(seed=3, citizens=1, patches=0))
        b = World(Config(seed=3, citizens=1, patches=0))
        for world in (a, b):
            world.citizens[0].x = world.citizens[0].y = 0
            world.citizens[0].food = 0
        b.food[(20, 10)] = 100
        a.step()
        b.step()
        self.assertEqual(a.citizens, b.citizens)

    def test_scarcity_causes_starvation(self):
        world = World(Config(patches=0))
        for _ in range(72):
            world.step()
        self.assertFalse(any(c.alive for c in world.citizens))
        self.assertEqual(sum(e["kind"] == "starve" for e in world.events), 20)


if __name__ == "__main__":
    unittest.main()
