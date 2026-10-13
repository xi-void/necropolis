import json
import unittest

from necropolis.simulation import Config, World, replay


class MemoryTests(unittest.TestCase):
    def test_remembered_food_guides_movement_without_remote_updates(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.occupation = "forager"
        c.x = c.y = 0
        c.food = 0
        world.food[(3, 0)] = 2
        world.perceive(c)
        c.x = 8
        world.food[(3, 0)] = 0
        world.perceive(c)
        world.act(c)
        self.assertEqual(c.x, 7)
        self.assertEqual(c.food_memory[0].amount, 2)
        c.x = 3
        world.perceive(c)
        self.assertEqual(c.food_memory[0].amount, 0)

    def test_food_memories_expire(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.x = c.y = 0
        world.food[(0, 0)] = 2
        world.perceive(c)
        c.x = 20
        world.tick = 73
        world.perceive(c)
        self.assertEqual(c.food_memory, [])

    def test_trade_builds_directional_trust_and_discount(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0, initial_trust=70))
        seller, buyer = world.citizens
        seller.occupation = "merchant"
        seller.food = 6
        buyer.food = 0
        seller.x = buyer.x = seller.y = buyer.y = 0
        world.perceive(buyer)
        world.perceive(seller)
        world.trade(buyer, seller)
        self.assertEqual(world.trust(seller, buyer), 75)
        self.assertEqual(world.trust(buyer, seller), 75)
        self.assertEqual(world.price(seller, buyer), 2)
        self.assertEqual(world.relationship(buyer, seller).trades, 1)
        self.assertTrue(any(m["kind"] == "trade" for m in buyer.memories))

    def test_low_trust_blocks_trade(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0, initial_trust=10))
        seller, buyer = world.citizens
        seller.food, buyer.food = 5, 0
        seller.x = buyer.x = seller.y = buyer.y = 0
        self.assertEqual(world.sellers(buyer), [])

    def test_unseen_encounters_and_events_are_not_remembered(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=3, patches=0))
        actor, nearby, distant = world.citizens
        actor.x = actor.y = nearby.x = nearby.y = 0
        distant.x, distant.y = 20, 10
        world.perceive(distant)
        world.emit("starve", actor.id)
        self.assertEqual(distant.relationships, [])
        self.assertEqual(distant.memories, [])
        self.assertEqual(nearby.memories[-1]["kind"], "starve")

    def test_serialized_replay_includes_memories(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47, initial_trust=80))
        for _ in range(240):
            world.step()
        record = json.loads(json.dumps(world.record()))
        self.assertEqual(replay(record).state(), world.state())


if __name__ == "__main__":
    unittest.main()
