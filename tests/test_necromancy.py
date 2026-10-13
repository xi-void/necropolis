import json
import unittest

from necropolis.observer import Observer
from necropolis.simulation import Config, World, replay


class NecromancyTests(unittest.TestCase):
    def prepared(self):
        world = World(Config(mine_count=0, citizens=4, grave_count=1))
        c = next(c for c in world.citizens if c.occupation == "necromancer")
        body = next(b for b in world.corpses if b.buried)
        c.x, c.y = body.x, body.y
        return world, c, body

    def test_finite_seeded_graveyard_and_independent_initialization(self):
        a, b = World(Config(mine_count=0, seed=47)), World(Config(mine_count=0, seed=47, necromancy=False, grave_count=0))
        self.assertEqual(a.food, b.food)
        self.assertEqual([(c.name, c.x, c.y, c.fatigue) for c in a.citizens],
                         [(c.name, c.x, c.y, c.fatigue) for c in b.citizens])
        self.assertEqual(len(a.graves), 4)
        self.assertEqual(sum(c.occupation == "necromancer" for c in a.citizens), 1)
        self.assertEqual(sum(c.money for c in a.citizens), 240)
        self.assertEqual(a.state(), World(Config(mine_count=0, seed=47)).state())
        comparison = World(Config(mine_count=0, seed=47, necromancy=False))
        self.assertEqual(a.graves, comparison.graves)
        self.assertEqual(a.corpses, comparison.corpses)
        ids = [c.id for c in a.citizens] + [g.id for g in a.graves] + [c.id for c in a.corpses]
        self.assertEqual(len(ids), len(set(ids)))

    def test_burial_preserves_body_and_does_not_invent_citizen_history(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=1, corpse_decay_hours=2))
        body = world.corpses[0]
        for _ in range(24):
            world.step()
        self.assertEqual(body.decay, 0)
        self.assertFalse(body.available)
        self.assertIsNone(body.citizen_id)
        self.assertIsNone(body.died_at)

    def test_exhume_empties_grave_and_animation_consumes_body_once(self):
        world, c, body = self.prepared()
        world.exhume(c, body)
        self.assertFalse(world.graves[0].occupied)
        self.assertTrue(body.available)
        self.assertFalse(body.preserved)
        world.animate(c, body)
        self.assertEqual(c.mana, 0)
        self.assertEqual(len(world.undead), 1)
        self.assertNotIn(body, world.corpses)
        self.assertEqual(world.undead[0].name, body.name)
        with self.assertRaises(ValueError):
            world.animate(c, body)
        for _ in range(100):
            world.step()
        self.assertEqual(len(world.graves), 1)
        self.assertFalse(world.graves[0].occupied)
        self.assertEqual(sum(e["kind"] == "grave_created" for e in world.events), 1)

    def test_local_knowledge_and_action_cost(self):
        world, c, body = self.prepared()
        c.x = (body.x + 8) % world.config.width
        world.perceive(c)
        self.assertEqual(c.body_memory, [])
        c.x, c.y = body.x, body.y
        world.perceive(c)
        c.food = 4
        world.act(c)
        self.assertEqual(world.events[-1]["kind"], "exhume")
        self.assertEqual(len(world.undead), 0)
        world.perceive(c)
        world.act(c)
        self.assertEqual(len(world.undead), 1)

    def test_insufficient_mana_and_sleep_prevent_animation(self):
        world, c, body = self.prepared()
        world.exhume(c, body)
        c.mana = 29
        with self.assertRaises(ValueError):
            world.animate(c, body)
        c.mana, c.sleeping = 30, True
        with self.assertRaises(ValueError):
            world.animate(c, body)

    def test_upkeep_failure_reactivation_and_keeper_death(self):
        world, c, body = self.prepared()
        world.exhume(c, body)
        world.animate(c, body)
        worker = world.undead[0]
        world.tick = worker.next_upkeep
        world.maintain_undead()
        self.assertFalse(worker.active)
        self.assertEqual(worker.integrity, 71)
        c.mana = 1
        world.maintain_undead()
        self.assertTrue(worker.active)
        self.assertEqual(c.mana, 0)
        world.die(c, "starvation")
        world.maintain_undead()
        self.assertFalse(worker.active)
        for _ in range(72):
            world.maintain_undead()
        self.assertEqual(world.undead, [])

    def test_exposed_body_decays_and_finite_pool_is_not_replenished(self):
        world, c, body = self.prepared()
        world.exhume(c, body)
        world.config = Config(mine_count=0, citizens=4, grave_count=1, necromancy=False)
        c.occupation = "forager"
        for _ in range(body.decay_hours):
            world.step()
        self.assertNotIn(body, world.corpses)
        self.assertFalse(world.graves[0].occupied)

    def test_range_and_mana_accounting(self):
        world, c, body = self.prepared()
        world.perceive(c)
        world.exhume(c, body)
        world.animate(c, body)
        world.magic_action(c)
        self.assertEqual(c.mana, 6)
        worker = world.undead[0]
        world.tick = 6
        world.maintain_undead()
        self.assertEqual(c.mana, 5)
        c.x = (worker.x + 10) % world.config.width
        world.maintain_undead()
        self.assertFalse(worker.active)

    def test_serialized_replay_and_detached_inspection(self):
        world = World(Config(mine_count=0, seed=1))
        for _ in range(240):
            world.step()
        self.assertEqual(replay(json.loads(json.dumps(world.record()))).state(), world.state())
        observer = Observer(world)
        grave = observer.inspect(("grave", world.graves[0].id))
        grave["occupied"] = "fake"
        self.assertIsInstance(world.graves[0].occupied, bool)


if __name__ == "__main__":
    unittest.main()
