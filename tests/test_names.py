import contextlib
import io
import unittest

from necropolis.__main__ import render
from necropolis.names import generate_names
from necropolis.simulation import Config, World


class NameTests(unittest.TestCase):
    def test_seeded_unique_names(self):
        names = generate_names(47, 448)
        self.assertEqual(names, generate_names(47, 448))
        self.assertEqual(len(set(names)), 448)
        self.assertNotEqual(names, generate_names(48, 448))
        self.assertTrue(all(len(name.split()) == 2 for name in names))

    def test_names_do_not_change_behavior(self):
        a, b = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47)), World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47))
        for c in b.citizens:
            c.name = "Someone Else"
        for _ in range(72):
            a.step()
            b.step()
        self.assertEqual(a.events, b.events)

    def test_trade_display_names_both_participants(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, citizens=2, patches=0))
        seller, buyer = world.citizens
        seller.food = 5
        world.trade(buyer, seller)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            render(world)
        self.assertIn(seller.name, output.getvalue())
        self.assertIn(buyer.name, output.getvalue())


if __name__ == "__main__":
    unittest.main()
