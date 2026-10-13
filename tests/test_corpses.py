import contextlib
import io
import json
import unittest

from necropolis.__main__ import inspect, render
from necropolis.simulation import Config, World, replay


class CorpseTests(unittest.TestCase):
    def test_death_creates_one_unique_body_and_preserves_resources(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0))
        c = world.citizens[0]
        c.food = 3
        world.die(c, "starvation")
        world.die(c, "starvation")
        self.assertEqual(len(world.corpses), 1)
        corpse = world.corpses[0]
        self.assertNotIn(corpse.id, world.citizens_by_id)
        self.assertEqual((corpse.citizen_id, corpse.name, corpse.x, corpse.y),
                         (c.id, c.name, c.x, c.y))
        self.assertEqual((corpse.died_at, corpse.cause, corpse.decay), (0, "starvation", 0))
        self.assertEqual(c.corpse_id, corpse.id)
        self.assertTrue(corpse.available)
        self.assertFalse(corpse.reanimated)
        self.assertEqual(world.food[(c.x, c.y)], 3)
        self.assertEqual(c.food, 0)
        self.assertEqual(sum(p.money for p in world.citizens), 24)
        world.die(world.citizens[1], "starvation")
        self.assertNotEqual(world.corpses[0].id, world.corpses[1].id)

    def test_starvation_path_creates_body_at_zero_age(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0))
        c = world.citizens[0]
        c.food, c.hunger = 0, 47
        world.step()
        self.assertEqual(world.corpses[0].decay, 0)
        self.assertEqual(world.corpses[0].died_at, 1)
        self.assertEqual([e["kind"] for e in world.events][-2:], ["starve", "corpse_created"])
        world.step()
        self.assertEqual(world.corpses[0].decay, 1)

    def test_decay_stages_removal_and_history_after_extinction(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0, corpse_decay_hours=3))
        c = world.citizens[0]
        world.die(c, "starvation")
        body_id = c.corpse_id
        world.step()
        self.assertEqual(world.corpses[0].stage, "decaying")
        world.step()
        self.assertEqual(world.corpses[0].stage, "skeletal")
        world.step()
        self.assertEqual(world.corpses, [])
        self.assertIs(world.citizens_by_id[c.id], c)
        self.assertEqual(c.corpse_id, body_id)
        self.assertEqual(world.events[-1]["kind"], "corpse_removed")
        self.assertEqual(world.events[-1]["corpse"], body_id)
        self.assertEqual(world.events[1]["name"], c.name)
        self.assertEqual(c.money, 12)

    def test_preserved_or_reanimated_bodies_do_not_decay(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0, corpse_decay_hours=1))
        for c in world.citizens:
            world.die(c, "starvation")
        preserved, animated = world.corpses
        preserved.preserved = True
        animated.reanimated = True
        world.step()
        self.assertEqual(len(world.corpses), 2)
        self.assertEqual((preserved.decay, animated.decay), (0, 0))
        self.assertTrue(preserved.available)
        self.assertFalse(animated.available)

    def test_bodies_sharing_tile_remain_separate(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0))
        for c in world.citizens:
            c.x = c.y = 0
            world.die(c, "starvation")
        self.assertEqual(len(world.corpses), 2)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            inspect(world)
            render(world)
        for corpse in world.corpses:
            self.assertIn(f"Body #{corpse.id}", output.getvalue())
        self.assertIn("Corpses 2", output.getvalue())

    def test_map_marker_disappears_after_decay(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=1, patches=0, corpse_decay_hours=1))
        world.citizens[0].x = world.citizens[0].y = 0
        world.die(world.citizens[0], "starvation")
        before, after = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(before):
            render(world)
        world.step()
        with contextlib.redirect_stdout(after):
            render(world)
        self.assertTrue(before.getvalue().splitlines()[2].startswith("|+"))
        self.assertTrue(after.getvalue().splitlines()[2].startswith('|"'))
        self.assertEqual(world.food[(0, 0)], 2)

    def test_json_replay_before_and_after_decay(self):
        for hours in (72, 120):
            world = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47, patches=0, corpse_decay_hours=24))
            for _ in range(hours):
                world.step()
            record = json.loads(json.dumps(world.record()))
            self.assertEqual(replay(record).state(), world.state())
            self.assertEqual(sum(e["kind"] == "corpse_created" for e in world.events), 20)
            if hours == 120:
                self.assertEqual(world.corpses, [])
                self.assertEqual(sum(e["kind"] == "corpse_removed" for e in world.events), 20)

    def test_invalid_decay_duration(self):
        with self.assertRaises(ValueError):
            Config(mine_count=0, necromancy=False, grave_count=0, corpse_decay_hours=0)


if __name__ == "__main__":
    unittest.main()
