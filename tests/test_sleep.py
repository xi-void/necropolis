import json
import unittest

from necropolis.simulation import Config, World, replay


class SleepTests(unittest.TestCase):
    def test_sleep_consumes_hour_and_recovers_without_work_or_perception(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=1))
        c = world.citizens[0]
        c.x, c.y = next(iter(world.patches))
        c.sleeping, c.fatigue, c.hunger = True, 80, 0
        world.step()
        self.assertEqual(c.fatigue, 80 - c.recovery_rate)
        self.assertEqual(c.hunger, 1)
        self.assertEqual(c.food, 2)
        self.assertEqual(c.food_memory, [])
        self.assertEqual([e["kind"] for e in world.events], ["sleep"])

    def test_exhaustion_starts_sleep_and_rest_wakes(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.fatigue = 80
        world.step()
        self.assertTrue(c.sleeping)
        self.assertEqual(world.events[0]["kind"], "sleep_start")
        c.fatigue = 5
        world.step()
        self.assertFalse(c.sleeping)
        self.assertEqual(c.fatigue, 0)
        self.assertEqual(world.events[-1]["reason"], "rested")

    def test_hunger_interrupts_sleep_to_eat(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.sleeping, c.fatigue, c.hunger = True, 70, 11
        world.step()
        self.assertFalse(c.sleeping)
        self.assertEqual((c.food, c.hunger), (1, 6))
        self.assertEqual(world.events[0]["reason"], "hunger")
        self.assertEqual(world.events[-1]["kind"], "eat")

    def test_desperate_hunger_wakes_to_seek_food_and_can_still_starve(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.sleeping, c.food, c.hunger, c.fatigue = True, 0, 23, 90
        world.step()
        self.assertFalse(c.sleeping)
        self.assertEqual(world.events[-1]["kind"], "move")
        c.hunger = 47
        world.step()
        self.assertFalse(c.alive)
        self.assertFalse(c.sleeping)

    def test_sleepers_cannot_sell_or_witness(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0))
        seller, buyer = world.citizens
        seller.x = buyer.x = seller.y = buyer.y = 0
        seller.sleeping, seller.food, buyer.food = True, 5, 0
        self.assertEqual(world.sellers(buyer), [])
        with self.assertRaises(ValueError):
            world.trade(buyer, seller)
        world.emit("starve", buyer.id)
        self.assertEqual(seller.memories, [])

    def test_empty_inventory_wakes_before_desperation(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=1))
        c = world.citizens[0]
        c.x, c.y = next(iter(world.patches))
        c.sleeping, c.food, c.hunger, c.fatigue = True, 0, 5, 70
        world.step()
        self.assertFalse(c.sleeping)
        self.assertEqual(c.food, 1)
        self.assertEqual(world.events[0]["reason"], "hunger")
        self.assertEqual(world.events[-1]["kind"], "produce")

    def test_hungry_tired_citizen_seeks_food_before_sleep(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=1))
        c = world.citizens[0]
        c.x, c.y = next(iter(world.patches))
        c.food, c.hunger, c.fatigue = 0, 8, 85
        world.step()
        self.assertFalse(c.sleeping)
        self.assertEqual(c.food, 1)

    def test_starting_sleep_does_not_add_awake_fatigue(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.fatigue = 80
        world.step()
        self.assertEqual(c.fatigue, 80 - c.recovery_rate)

    def test_individual_needs_are_seeded_and_change_sleep_timing(self):
        a, b = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47)), World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47))
        needs = [(c.fatigue_rate, c.recovery_rate, c.fatigue) for c in a.citizens]
        self.assertEqual(needs, [(c.fatigue_rate, c.recovery_rate, c.fatigue) for c in b.citizens])
        self.assertGreater(len(set(needs)), 1)
        slow, fast = a.citizens[:2]
        slow.fatigue = fast.fatigue = 75
        slow.hunger = fast.hunger = 0
        slow.fatigue_rate, fast.fatigue_rate = 3, 5
        a.step()
        self.assertFalse(slow.sleeping)
        self.assertTrue(fast.sleeping)

    def test_sleep_bounds_and_serialized_replay(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47))
        for _ in range(240):
            world.step()
            self.assertTrue(all(0 <= c.fatigue <= 100 for c in world.citizens))
        self.assertTrue(any(e["kind"] == "sleep_start" for e in world.events))
        self.assertEqual(replay(json.loads(json.dumps(world.record()))).state(), world.state())


if __name__ == "__main__":
    unittest.main()
