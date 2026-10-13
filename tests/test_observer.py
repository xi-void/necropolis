import importlib.util
import os
import unittest

from necropolis.observer import Camera, Observer
from necropolis.simulation import Config, World


class ObserverTests(unittest.TestCase):
    def test_adapter_preserves_seeded_results(self):
        a, b = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47)), World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47))
        observer = Observer(b)
        for _ in range(72):
            a.step()
            observer.step()
        self.assertEqual(a.record(), b.record())

    def test_pause_and_bounded_speed(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0))
        observer = Observer(world)
        observer.update(10)
        self.assertEqual(world.tick, 0)
        observer.step()
        self.assertEqual(world.tick, 1)
        observer.toggle_pause()
        observer.speed = 3
        self.assertLessEqual(observer.update(100), 8)
        tick = world.tick
        observer.step()
        self.assertEqual(world.tick, tick)
        observer.toggle_pause()
        observer.update(10)
        self.assertEqual(world.tick, tick)

    def test_inspection_is_detached_and_refresh_does_not_duplicate_events(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0))
        observer = Observer(world)
        observer.step()
        original = world.record()
        citizen = observer.inspect(("citizen", 1))
        citizen["money"] = 999
        citizen["memories"].append({"fake": True})
        event = observer.event(0)
        event["kind"] = "fake"
        for _ in range(4):
            observer.refresh()
        self.assertEqual(original, world.record())
        self.assertEqual(len(observer.logs["all"]), len(world.events))

    def test_camera_conversion_zoom_anchor_and_cell_selection(self):
        camera = Camera(x=2.5, y=-3, cell=20)
        origin = (40, 80)
        point = camera.screen((5.5, 2.5), origin)
        self.assertEqual(camera.tile(point, origin), (5, 2))
        before = camera.screen_to_world(point, origin)
        camera.zoom(1.5, point, origin)
        after = camera.screen_to_world(point, origin)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])
        observer = Observer(World(Config(mine_count=0, necromancy=False, grave_count=0)))
        c = observer.citizens[1]
        self.assertIn(("citizen", 1), observer.cells[(c["x"], c["y"])])

    def test_deceased_identity_survives_corpse_removal(self):
        world = World(Config(mine_count=0, necromancy=False, grave_count=0, patches=0, corpse_decay_hours=1))
        observer = Observer(world)
        for _ in range(72):
            observer.step()
        self.assertFalse(observer.inspect(("citizen", 1))["alive"])
        self.assertIn(1, observer.deaths)
        self.assertEqual(observer.corpses, {})


@unittest.skipUnless(importlib.util.find_spec("pygame"), "optional pygame-ce not installed")
class GraphicalTests(unittest.TestCase):
    def setUp(self):
        self.previous_driver = os.environ.get("SDL_VIDEODRIVER")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        from necropolis.gui import Application
        self.world = World(Config(mine_count=0, necromancy=False, grave_count=0, seed=47))
        self.app = Application(self.world, size=(1280, 800))

    def tearDown(self):
        import pygame
        pygame.quit()
        if self.previous_driver is None:
            os.environ.pop("SDL_VIDEODRIVER", None)
        else:
            os.environ["SDL_VIDEODRIVER"] = self.previous_driver

    def test_render_and_inspect_do_not_mutate_engine_or_rng(self):
        state, rng = self.world.record(), self.world.rng.getstate()
        for scale in (1.0, 1.5):
            self.app.set_scale(scale)
            self.app.layout()
            self.app.selection = ("citizen", 1)
            self.app.draw()
            self.app.sidebar_lines()
        self.assertEqual(state, self.world.record())
        self.assertEqual(rng, self.world.rng.getstate())

    def test_keyboard_step_pause_speed_help(self):
        import pygame
        def press(key):
            self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
        press(pygame.K_PERIOD)
        self.assertEqual(self.world.tick, 1)
        press(pygame.K_SPACE)
        press(pygame.K_4)
        self.assertFalse(self.app.observer.paused)
        self.assertEqual(self.app.observer.speed, 3)
        press(pygame.K_PERIOD)
        self.assertEqual(self.world.tick, 1)
        press(pygame.K_F1)
        self.app.update(.2)
        self.assertEqual(self.world.tick, 1)
        press(pygame.K_ESCAPE)
        self.assertFalse(self.app.help)

    def test_selection_follow_and_resize(self):
        import pygame
        c = self.app.observer.citizens[1]
        point = self.app.camera.screen((c["x"] + .5, c["y"] + .5), self.app.map_rect.topleft)
        self.app.draw()
        self.app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.assertIsNotNone(self.app.selection)
        self.app.selection = ("citizen", 1)
        self.app.follow = True
        self.app.update(0)
        # Emulate SDL's resized surface; the app must adopt it, not set a new mode.
        pygame.display.set_mode((1920, 1080), pygame.RESIZABLE)
        self.app.handle(pygame.event.Event(pygame.VIDEORESIZE, w=1920, h=1080))
        self.app.set_scale(1.5)
        self.app.layout()
        self.app.draw()
        self.assertEqual(self.app.screen.get_size(), (1920, 1080))

    def test_resize_notifications_never_recreate_display(self):
        import pygame
        from unittest.mock import patch
        for kind in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
            with patch.object(pygame.display, "set_mode") as set_mode:
                for _ in range(10):
                    self.app.handle(pygame.event.Event(kind, w=600, h=400, x=600, y=400))
                self.app.draw()
                set_mode.assert_not_called()
        self.assertEqual(self.world.tick, 0)

    def test_complete_frame_presented_and_resized_without_notification(self):
        import pygame
        self.assertIsNot(self.app.screen, pygame.display.get_surface())
        self.app.draw()
        self.assertEqual(pygame.image.tobytes(self.app.screen, "RGB"),
                         pygame.image.tobytes(pygame.display.get_surface(), "RGB"))
        pygame.display.set_mode((900, 600), pygame.RESIZABLE)
        self.app.draw()
        self.assertEqual(self.app.screen.get_size(), (900, 600))
        self.assertEqual(self.app.side_rect.right, 900)

    def test_actual_window_loop_smoke(self):
        self.app.run(max_frames=3)
        self.assertEqual(self.world.tick, 0)

    def test_economy_dashboard_is_read_only_and_keeps_controls_available(self):
        import pygame
        original = self.world.record()
        rng = self.world.rng.getstate()
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
        self.assertTrue(self.app.economy_view)
        self.app.draw()
        self.assertEqual(self.world.record(), original)
        self.assertEqual(self.world.rng.getstate(), rng)
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PERIOD))
        self.assertEqual(self.world.tick, 1)
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(self.app.economy_view)

    def test_running_frames_present_complete_surface(self):
        import pygame
        from unittest.mock import patch
        self.app.observer.toggle_pause()
        self.app.observer.speed = 3
        with patch.object(pygame.display, "set_mode") as set_mode:
            for _ in range(20):
                self.app.update(1 / 60)
                self.app.draw()
                self.assertEqual(pygame.image.tobytes(self.app.screen, "RGB"),
                                 pygame.image.tobytes(pygame.display.get_surface(), "RGB"))
            set_mode.assert_not_called()
        self.assertGreater(self.world.tick, 0)


if __name__ == "__main__":
    unittest.main()
