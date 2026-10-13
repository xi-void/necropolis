"""Software-rendered pygame-ce observer; no pygame imports in the engine."""

from functools import lru_cache
import math
import os
import textwrap

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from . import __version__
from .observer import Camera, Observer, category
from .economy import citizen_conditions


BG = "#16161e"
PANEL = "#1a1b26"
TEXT = "#c0caf5"
MUTED = "#737aa2"
LINE = "#292e42"
ACCENT = "#7aa2f7"
COLORS = {"farmer": "#9ece6a", "merchant": "#e0af68", "forager": "#7dcfff",
          "necromancer": "#bb9af7", "undead": "#c099ff", "grave": "#737aa2",
          "mine": "#a9b1d6", "miner": "#ff9e64", "ore": "#e0af68",
          "corpse": "#f7768e", "food": "#9ece6a", "sleep": "#bb9af7"}
HELP = ["SPACE  pause / resume", ". / RIGHT  one hour when paused",
        "E / Economy button  rates and economic history",
        "1-4  speed: 1 / 4 / 16 / 64 hours/sec",
        "WASD  pan; arrows pan while running",
        "Wheel over map  zoom at cursor", "Click map  select; repeat to cycle a crowd",
        "F  follow selected citizen", "TAB  next citizen (including deceased)",
        "G  grid; HOME  fit map", "Wheel over sidebar/log  scroll",
        "L / Filter button  event category", "+ / -  interface text size",
        "F1  shortcuts; ESC  close help / clear selection",
        "Close window to quit; --log saves the run"]


class Application:
    def __init__(self, world, scale=1.0, size=None):
        pygame.display.init()
        pygame.font.init()
        desktop = pygame.display.get_desktop_sizes()[0]
        size = size or (min(1280, desktop[0]), min(800, desktop[1]))
        self.display = pygame.display.set_mode(size, pygame.RESIZABLE)
        # Draw into a private buffer; expose only complete frames to the window.
        self.screen = pygame.Surface(self.display.get_size()).convert()
        pygame.display.set_caption("NECROPOLIS // Observer")
        self.observer = Observer(world)
        self.camera = Camera()
        self.selection = None
        self.follow = self.grid = self.help = False
        self.running = True
        self.economy_view = False
        self.sidebar_offset = self.log_offset = 0
        self.filters = list(self.observer.logs)
        self.filter_index = 0
        self.buttons = []
        self.set_scale(scale)
        self.layout()
        self.fit()

    def set_scale(self, scale):
        self.scale = min(2, max(0.75, scale))
        path = pygame.font.match_font("dejavusansmono,liberationmono,consolas,monospace")
        self.font = pygame.font.Font(path, round(16 * self.scale))
        self.row = self.font.get_linesize() + 4
        self.text_surface.cache_clear()
        self.glyph.cache_clear()

    @lru_cache(maxsize=512)
    def text_surface(self, value, color=TEXT):
        return self.font.render(str(value), True, color)

    @lru_cache(maxsize=256)
    def glyph(self, value, color, size):
        return self.map_font(size).render(value, True, color)

    @lru_cache(maxsize=64)
    def map_font(self, size):
        path = pygame.font.match_font("dejavusansmono,liberationmono,consolas,monospace")
        return pygame.font.Font(path, size)

    def layout(self):
        w, h = self.screen.get_size()
        top = self.row * 2 + 16
        side = min(int(w * 0.39), round(380 * self.scale))
        log_h = min(int(h * 0.3), self.row * 7 + 16)
        self.map_rect = pygame.Rect(0, top, max(1, w - side), max(1, h - top - log_h))
        self.side_rect = pygame.Rect(w - side, top, side, max(1, h - top))
        self.log_rect = pygame.Rect(0, h - log_h, w - side, log_h)

    def sync_display(self):
        """SDL resizes its display surface; never recreate the window in response."""
        display = pygame.display.get_surface()
        if display is None:
            return
        self.display = display
        if self.screen.get_size() != display.get_size():
            self.screen = pygame.Surface(display.get_size()).convert()
            self.layout()

    def fit(self):
        config = self.observer.world.config
        self.camera.cell = max(12, min(48, (self.map_rect.w - 32) / config.width,
                                             (self.map_rect.h - 32) / config.height))
        self.camera.center((config.width / 2 - .5, config.height / 2 - .5), self.map_rect.size)

    def button(self, label, action, x, y):
        surface = self.text_surface(label, ACCENT)
        rect = pygame.Rect(x, y, surface.get_width() + 16, self.row)
        pygame.draw.rect(self.screen, LINE, rect, border_radius=3)
        self.screen.blit(surface, (x + 8, y + 2))
        self.buttons.append((rect, action))
        return rect.right + 8

    def dispatch(self, action):
        o = self.observer
        if action == "pause":
            o.toggle_pause()
        elif action == "step":
            o.step()
        elif action.startswith("speed"):
            o.speed = int(action[-1])
            o.credit = 0
        elif action == "filter":
            self.filter_index = (self.filter_index + 1) % len(self.filters)
            self.log_offset = 0
        elif action == "follow":
            self.follow = not self.follow
        elif action == "economy":
            self.economy_view = not self.economy_view

    def handle(self, event):
        o = self.observer
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
            self.sync_display()
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                if self.help:
                    self.help = False
                elif self.economy_view:
                    self.economy_view = False
                else:
                    self.selection = None
                    self.follow = False
                    self.sidebar_offset = 0
            elif key == pygame.K_F1:
                self.help = not self.help
            elif not self.help:
                if key == pygame.K_SPACE:
                    self.dispatch("pause")
                elif key == pygame.K_PERIOD or (key == pygame.K_RIGHT and o.paused):
                    self.dispatch("step")
                elif pygame.K_1 <= key <= pygame.K_4:
                    self.dispatch(f"speed{key - pygame.K_1}")
                elif key == pygame.K_f:
                    self.dispatch("follow")
                elif key == pygame.K_g:
                    self.grid = not self.grid
                elif key == pygame.K_l:
                    self.dispatch("filter")
                elif key == pygame.K_e:
                    self.dispatch("economy")
                elif key == pygame.K_HOME:
                    self.follow = False
                    self.fit()
                elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_MINUS):
                    self.set_scale(self.scale + (-.1 if key == pygame.K_MINUS else .1))
                    self.layout()
                elif key == pygame.K_TAB:
                    ids = list(o.citizens)
                    current = self.selection[1] if self.selection and self.selection[0] == "citizen" else None
                    index = (ids.index(current) + 1) % len(ids) if current in ids else 0
                    self.selection = ("citizen", ids[index])
                    self.sidebar_offset = 0
        elif event.type == pygame.MOUSEWHEEL and not self.help:
            if self.economy_view:
                return
            pos = pygame.mouse.get_pos()
            if self.map_rect.collidepoint(pos):
                self.camera.zoom(1.15 ** event.y, pos, self.map_rect.topleft)
            elif self.side_rect.collidepoint(pos):
                self.sidebar_offset = max(0, self.sidebar_offset - event.y * 3)
            elif self.log_rect.collidepoint(pos):
                self.log_offset = max(0, self.log_offset + event.y * 3)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.help:
            if self.economy_view and event.pos[1] >= self.map_rect.top:
                return
            for rect, action in self.buttons:
                if rect.collidepoint(event.pos):
                    self.dispatch(action)
                    return
            if self.economy_view:
                return
            for rect, index in getattr(self, "event_rows", []):
                if rect.collidepoint(event.pos):
                    self.selection = ("event", index)
                    self.sidebar_offset = 0
                    self.follow = False
                    return
            if self.map_rect.collidepoint(event.pos):
                tile = self.camera.tile(event.pos, self.map_rect.topleft)
                choices = o.cells.get(tile, [])
                index = (choices.index(self.selection) + 1) % len(choices) if self.selection in choices else 0
                self.selection = choices[index] if choices else None
                self.sidebar_offset = 0

    def update(self, elapsed, keys=None):
        if not self.help:
            old_count = len(self.observer.logs[self.filters[self.filter_index]])
            self.observer.update(elapsed)
            if self.log_offset:
                self.log_offset += len(self.observer.logs[self.filters[self.filter_index]]) - old_count
        keys = keys if keys is not None else pygame.key.get_pressed()
        if not self.help and not self.economy_view:
            dx = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
            dy = int(keys[pygame.K_s]) - int(keys[pygame.K_w])
            if not self.observer.paused:
                dx += int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
                dy += int(keys[pygame.K_DOWN]) - int(keys[pygame.K_UP])
            if dx or dy:
                self.follow = False
                self.camera.x += dx * 350 * min(elapsed, .1) / self.camera.cell
                self.camera.y += dy * 350 * min(elapsed, .1) / self.camera.cell
        selected = self.observer.inspect(self.selection)
        if self.follow and selected and self.selection[0] == "citizen":
            self.camera.center((selected["x"], selected["y"]), self.map_rect.size)

    def draw_map(self):
        o, cam = self.observer, self.camera
        self.screen.set_clip(self.map_rect)
        width, height = o.world.config.width, o.world.config.height
        x0, y0 = max(0, math.floor(cam.x)), max(0, math.floor(cam.y))
        x1 = min(width, math.ceil(cam.x + self.map_rect.w / cam.cell))
        y1 = min(height, math.ceil(cam.y + self.map_rect.h / cam.cell))
        for y in range(y0, y1):
            for x in range(x0, x1):
                p = (x, y)
                sx, sy = cam.screen(p, self.map_rect.topleft)
                rect = pygame.Rect(round(sx), round(sy), math.ceil(cam.cell), math.ceil(cam.cell))
                pygame.draw.rect(self.screen, PANEL if (x + y) % 2 else BG, rect)
                glyph, color = ".", LINE
                if o.food.get(p, 0):
                    glyph, color = '"', COLORS["food"]
                entities = o.cells.get(p, [])
                mines = [o.mines[item[1]] for item in entities if item[0] == "mine"]
                if mines:
                    glyph, color = ("^" if mines[0]["remaining"] else "v"), COLORS["mine"]
                if o.ground_ore.get(p, 0):
                    glyph, color = "*", COLORS["ore"]
                bodies = [item for item in entities if item[0] == "corpse"]
                graves = [o.graves[item[1]] for item in entities if item[0] == "grave"]
                undead = [o.undead[item[1]] for item in entities if item[0] == "undead"]
                citizens = [o.citizens[item[1]] for item in entities if item[0] == "citizen"]
                if graves:
                    glyph, color = ("T" if graves[0]["occupied"] else "_"), COLORS["grave"]
                if bodies:
                    glyph, color = "+", COLORS["corpse"]
                if undead:
                    glyph, color = ("U" if undead[0]["active"] else "u"), COLORS["undead"]
                if citizens:
                    c = citizens[0]
                    glyph = "&" if len(citizens) > 1 else ("z" if c["sleeping"] else {"farmer": "F", "merchant": "M", "forager": "@", "necromancer": "N", "miner": "P"}.get(c["occupation"], "@"))
                    color = COLORS["sleep"] if c["sleeping"] else COLORS.get(c["occupation"], ACCENT)
                surface = self.glyph(glyph, color, max(10, int(cam.cell * .78)))
                self.screen.blit(surface, surface.get_rect(center=rect.center))
                if self.grid:
                    pygame.draw.rect(self.screen, LINE, rect, 1)
                if self.selection in entities:
                    pygame.draw.rect(self.screen, ACCENT, rect, 2)
        self.screen.set_clip(None)

    def sidebar_lines(self):
        o = self.observer
        selected = o.inspect(self.selection)
        if selected is None:
            return ["SETTLEMENT", ""] + o.stats + ["", "F farmer / M merchant / @ forager", "N necromancer / P miner", "U active / u inactive undead", "^ mine / v exhausted / * ore", "T grave / _ empty grave", "z sleeping / + corpse / & crowd", "", "Click an entity to inspect.", "TAB cycles all citizen records.", "F1: keyboard shortcuts"]
        kind, identifier = self.selection
        if kind == "event":
            return ["HISTORICAL EVENT", ""] + [f"{key}: {value}" for key, value in selected.items()]
        if kind == "food":
            return ["FOOD", f"Location: ({selected['x']}, {selected['y']})", f"Units: {selected['food']}"]
        if kind == "ore":
            return ["DROPPED ORE", f"Location: ({selected['x']}, {selected['y']})", f"Units: {selected['ore']}"]
        if kind == "mine":
            return ["MINE", f"Site #{identifier}", f"Location: ({selected['x']}, {selected['y']})",
                    f"Remaining ore: {selected['remaining']}/{selected['initial']}", "Finite deposit: does not regenerate"]
        if kind == "grave":
            body = o.corpses.get(selected["corpse_id"])
            return ["GRAVE", f"Grave #{identifier}", f"Location: ({selected['x']}, {selected['y']})",
                    f"Occupied: {selected['occupied']}", f"Historical body #{selected['corpse_id']}",
                    body["name"] if body else "Body exhumed or removed"]
        if kind == "undead":
            return ["UNDEAD", selected["name"], f"Entity #{identifier} / body #{selected['corpse_id']}",
                    f"Keeper: {o.citizens[selected['keeper_id']]['name']}",
                    f"Location: ({selected['x']}, {selected['y']})", f"Active: {selected['active']}",
                    f"Integrity: {selected['integrity']}/72", f"Next upkeep: hour {selected['next_upkeep']}",
                    f"Condition: {o.worker_statuses[identifier]}", f"Assignment: {selected['assignment']}", f"Mine: {selected['mine_id']}", f"Carried ore: {selected['ore']}/8"]
        if kind == "corpse":
            return ["CORPSE", selected["name"], f"Body #{identifier} / citizen #{selected['citizen_id']}",
                    f"Location: ({selected['x']}, {selected['y']})", ("Death time: unknown" if selected['died_at'] is None else f"Died at hour {selected['died_at']}"),
                    f"Cause: {selected['cause']}", f"Decay: {selected['decay']}/{selected['decay_hours']}h",
                    f"Preserved: {selected['preserved']}", f"Reanimated: {selected['reanimated']}"]
        c = selected
        lines = [c["name"], f"Citizen #{c['id']} / {c['occupation']}",
                 f"Status: {'alive' if c['alive'] else 'deceased'}", f"Location: ({c['x']}, {c['y']})",
                 f"Latest action: {o.activities.get(c['id'], 'not yet observed')}",
                 f"Hunger: {c['hunger']} / 48", f"Fatigue: {c['fatigue']} / 100",
                 f"Sleep: {'asleep' if c['sleeping'] else 'awake'}",
                 f"Fatigue +{c['fatigue_rate']}/h / recovery -{c['recovery_rate']}/h",
                 f"Food: {c['food']} / Money: {c['money']}", f"Ore: {c['ore']}/8"]
        conditions = citizen_conditions(c)
        if conditions:
            lines += ["Economic conditions: " + ", ".join(conditions)]
        if c["occupation"] == "necromancer":
            lines += [f"Mana: {c['mana']}/60", f"Known bodies: {len(c['body_memory'])}"]
        if c["corpse_id"] is not None:
            lines += [f"Body #{c['corpse_id']}: {'present' if c['corpse_id'] in o.corpses else 'removed'}"]
            death = o.deaths.get(c["id"])
            if death:
                lines += [f"Death: hour {death['tick']} / {death['cause']}"]
        lines += ["", "RELATIONSHIPS"]
        for r in c["relationships"]:
            lines += [f"{o.citizens[r['id']]['name']} #{r['id']}", f" trust {r['trust']} / trades {r['trades']} / seen {o.snapshot['tick'] - r['seen']}h ago"]
        lines += ["", "RECENT PERSONAL MEMORIES"]
        for m in c["memories"]:
            lines.append(f"h{m['tick']} {m['kind']} / #{m['citizen']}")
        lines += ["", "FOOD KNOWLEDGE"]
        for m in c["food_memory"]:
            lines.append(f"({m['x']},{m['y']}) {m['amount']} units / seen {o.snapshot['tick'] - m['seen']}h ago")
        lines += ["", "MINE KNOWLEDGE"]
        for m in c["mine_memory"]:
            lines.append(f"Site #{m['id']} ({m['x']},{m['y']}) ore={m['remaining']} / seen {o.snapshot['tick'] - m['seen']}h ago")
        return lines

    def draw_sidebar(self):
        rect = self.side_rect
        pygame.draw.rect(self.screen, PANEL, rect)
        self.screen.set_clip(rect)
        self.button("Follow: " + ("ON" if self.follow else "OFF"), "follow", rect.x + 10, rect.y + 8)
        columns = max(8, (rect.w - 24) // max(1, self.font.size("M")[0]))
        lines = [part for line in self.sidebar_lines() for part in (textwrap.wrap(line, columns) or [""])]
        visible = max(1, (rect.h - self.row - 24) // self.row)
        self.sidebar_offset = min(self.sidebar_offset, max(0, len(lines) - visible))
        for i, line in enumerate(lines[self.sidebar_offset:self.sidebar_offset + visible]):
            self.screen.blit(self.text_surface(line), (rect.x + 12, rect.y + self.row + 20 + i * self.row))
        self.screen.set_clip(None)

    def event_text(self, event):
        who = self.observer.citizens.get(event.get("citizen"), {}).get("name", "World")
        details = " ".join(f"{k}={v}" for k, v in event.items() if k not in ("tick", "citizen", "kind", "name"))
        return f"D{event['tick'] // 24 + 1:04d} {event['tick'] % 24:02d}:00 {who}: {event['kind']} {details}"

    def draw_log(self):
        self.event_rows = []
        rect = self.log_rect
        pygame.draw.rect(self.screen, PANEL, rect)
        self.screen.set_clip(rect)
        group = self.filters[self.filter_index]
        self.button("Events: " + group, "filter", rect.x + 10, rect.y + 6)
        indexes = self.observer.logs[group]
        visible = max(1, (rect.h - self.row - 12) // self.row)
        self.log_offset = min(self.log_offset, max(0, len(indexes) - visible))
        end = len(indexes) - self.log_offset
        selected = indexes[max(0, end - visible):end]
        for row, index in enumerate(selected):
            event = self.observer.event(index)
            color = COLORS["corpse"] if category(event["kind"]) == "mortality" else TEXT
            if category(event["kind"]) == "magic":
                color = COLORS["sleep"]
            line = self.event_text(event)
            # Fit long events without rendering huge surfaces; full event remains in JSON.
            columns = max(8, (rect.w - 20) // max(1, self.font.size("M")[0]))
            self.screen.blit(self.text_surface(line[:columns], color), (rect.x + 10, rect.y + self.row + 10 + row * self.row))
            self.event_rows.append((pygame.Rect(rect.x, rect.y + self.row + 10 + row * self.row,
                                                rect.w, self.row), index))
        self.screen.set_clip(None)

    def draw_economy(self):
        o = self.observer
        e = o.snapshot["economy"]
        r = e["rates"]
        w, h = self.screen.get_size()
        top = self.map_rect.top
        pygame.draw.rect(self.screen, PANEL, (0, top, w, h - top))
        columns = max(12, (w - 32) // max(1, self.font.size("M")[0]))
        lines = [f"ECONOMY // trailing {e['window_hours']}h, normalized rates per day // E or ESC to close",
                 f"Food/day: produced {r.get('food_produced', 0):.1f}  consumed {r.get('food_consumed', 0):.1f}  imported {r.get('food_imported', 0):.1f}  net {r['food_balance']:+.1f}",
                 f"Ore/day: living {r.get('ore_living', 0):.1f}  undead {r.get('ore_undead', 0):.1f}  exports {r.get('ore_exported', 0):.1f}  export slots left today {e['export_slots']}",
                 f"Mana/day: regenerated {r.get('mana_replenished', 0):.1f}  animation {r.get('mana_animation', 0):.1f}  upkeep {r.get('mana_upkeep', 0):.1f}"]
        wrapped = [part for line in lines for part in textwrap.wrap(line, columns)]
        for i, line in enumerate(wrapped):
            self.screen.blit(self.text_surface(line), (16, top + 8 + i * self.row))
        start = top + 16 + len(wrapped) * self.row
        chart_w = max(1, (w - 48) // 2)
        chart_h = max(30, (h - start - 24) // 2)
        rows = o.economy_history[-120:]
        series = [("Living population", "living", ACCENT), ("Food stock (stored + wild)", "food", COLORS["food"]),
                  ("Ore stock (held + dropped)", "ore", COLORS["ore"]), ("Living coin inequality / Gini", "wealth_gini", COLORS["sleep"])]
        for index, (title, key, color) in enumerate(series):
            rect = pygame.Rect(16 + index % 2 * (chart_w + 16), start + index // 2 * chart_h, chart_w, chart_h - 8)
            pygame.draw.rect(self.screen, LINE, rect, 1)
            latest = rows[-1][key] if rows else 0
            title = f"{title}: {latest:.3f}" if key == "wealth_gini" else f"{title}: {latest}"
            self.screen.blit(self.text_surface(title[:max(8, chart_w // self.font.size('M')[0])], color), (rect.x + 8, rect.y + 6))
            plot = pygame.Rect(rect.x + 16, rect.y + self.row + 12, max(1, rect.w - 32), max(1, rect.h - self.row * 2 - 24))
            values = [row[key] for row in rows]
            maximum = 1 if key == "wealth_gini" else max([1] + values)
            points = [(round(plot.x + i * plot.w / max(1, len(values) - 1)),
                       round(plot.bottom - value * plot.h / maximum)) for i, value in enumerate(values)]
            if len(points) > 1:
                pygame.draw.lines(self.screen, color, False, points, 2)
            elif points:
                pygame.draw.circle(self.screen, color, points[0], 3)
            label = f"0..{maximum:.3f}" if key == "wealth_gini" else f"0..{maximum}"
            if rows:
                label += f" | h{rows[0]['tick']}..h{rows[-1]['tick']}"
            self.screen.blit(self.text_surface(label, MUTED), (rect.x + 8, rect.bottom - self.row))

    def draw(self):
        self.sync_display()
        self.buttons = []
        self.screen.fill(BG)
        o = self.observer
        tick = o.snapshot["tick"]
        state = "PAUSED" if o.paused else ("HELP (time stopped)" if self.help else "RUNNING")
        status = f"NECROPOLIS {__version__} | D{tick // 24 + 1:04d} {tick % 24:02d}:00 | Seed {o.world.config.seed} | {state} | {o.SPEEDS[o.speed]}h/s"
        self.screen.blit(self.text_surface(status), (10, 6))
        x = self.button("Resume" if o.paused else "Pause", "pause", 10, self.row + 6)
        x = self.button("Step", "step", x, self.row + 6)
        for i, speed in enumerate(o.SPEEDS):
            x = self.button(f"{'*' if o.speed == i else ''}{speed}h/s", f"speed{i}", x, self.row + 6)
        self.button("Economy [E]", "economy", x, self.row + 6)
        self.draw_map()
        self.draw_sidebar()
        self.draw_log()
        if self.economy_view:
            self.draw_economy()
        if self.help:
            shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 220))
            self.screen.blit(shade, (0, 0))
            for i, line in enumerate(["NECROPOLIS // SHORTCUTS", ""] + HELP):
                self.screen.blit(self.text_surface(line), (24, 24 + i * self.row))
        self.display.blit(self.screen, (0, 0))
        pygame.display.flip()

    def run(self, max_frames=None):
        clock = pygame.time.Clock()
        frames = 0
        try:
            while self.running and (max_frames is None or frames < max_frames):
                elapsed = clock.tick(60) / 1000
                for event in pygame.event.get():
                    self.handle(event)
                self.update(elapsed)
                self.draw()
                frames += 1
        finally:
            pygame.quit()


def run(world, scale=1.0):
    Application(world, scale=scale).run()
