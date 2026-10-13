"""Display-independent observer adapter. Inspection returns detached data."""

from copy import deepcopy
from dataclasses import dataclass
import math
import time
from .economy import worker_status


def category(kind):
    if kind in ("exhume", "grave_created"):
        return "magic"
    if kind in ("starve", "death") or kind.startswith("corpse_"):
        return "mortality"
    if kind in ("trade", "trade_ore", "gather", "produce", "grow", "mine_ore", "ore_export", "ore_delivered", "ore_collected"):
        return "economy"
    if kind in ("eat", "sleep", "sleep_start", "wake"):
        return "needs"
    if any(word in kind for word in ("mana", "animate", "undead", "magic")):
        return "magic"
    return "other"


class Observer:
    SPEEDS = (1, 4, 16, 64)

    def __init__(self, world):
        self.world = world
        self.paused = True
        self.speed = 0
        self.credit = 0.0
        self.event_cursor = 0
        self.logs = {key: [] for key in ("notable", "all", "mortality", "economy", "needs", "magic")}
        self.activities = {}
        self.trade_count = 0
        self.deaths = {}
        self.economy_history = []
        self.refresh()

    def refresh(self):
        for index in range(self.event_cursor, len(self.world.events)):
            event = self.world.events[index]
            if event["kind"] in ("trade", "trade_ore"):
                self.trade_count += 1
            if event["kind"] in ("death", "starve"):
                self.deaths[event["citizen"]] = deepcopy(event)
            self.logs["all"].append(index)
            group = category(event["kind"])
            if group in self.logs:
                self.logs[group].append(index)
            if event["kind"] not in ("move", "undead_move", "grow", "sleep", "rest"):
                self.logs["notable"].append(index)
            if (event.get("citizen") and not event["kind"].startswith("corpse_")
                    and event["kind"] not in ("mana_upkeep", "undead_active", "undead_inactive", "undead_removed", "undead_move", "mine_ore", "ore_delivered")):
                self.activities[event["citizen"]] = event["kind"]
            if event["kind"] == "mine_ore" and event.get("undead") is None:
                self.activities[event["citizen"]] = "mine_ore"
        self.event_cursor = len(self.world.events)
        self.snapshot = self.world.state()
        self.economy_history.extend(deepcopy(self.world.economy.history[len(self.economy_history):]))
        self.citizens = {c["id"]: c for c in self.snapshot["citizens"]}
        self.corpses = {c["id"]: c for c in self.snapshot["corpses"]}
        self.graves = {g["id"]: g for g in self.snapshot["graves"]}
        self.undead = {u["id"]: u for u in self.snapshot["undead"]}
        self.mines = {m["id"]: m for m in self.snapshot["mines"]}
        self.worker_statuses = {u["id"]: worker_status(u, self.citizens, self.mines, self.snapshot["tick"])
                                for u in self.undead.values()}
        self.ground_ore = {(x, y): amount for x, y, amount in self.snapshot["ground_ore"]}
        self.food = {(x, y): amount for x, y, amount in self.snapshot["food"]}
        self.cells = {}
        for c in self.snapshot["citizens"]:
            if c["alive"]:
                self.cells.setdefault((c["x"], c["y"]), []).append(("citizen", c["id"]))
        for c in self.snapshot["corpses"]:
            if not c["reanimated"] and not c["buried"]:
                self.cells.setdefault((c["x"], c["y"]), []).append(("corpse", c["id"]))
        for kind, collection in (("undead", self.undead), ("grave", self.graves), ("mine", self.mines)):
            for entity in collection.values():
                self.cells.setdefault((entity["x"], entity["y"]), []).append((kind, entity["id"]))
        for p, amount in self.ground_ore.items():
            if amount:
                self.cells.setdefault(p, []).append(("ore", p))
        for p, amount in self.food.items():
            if amount:
                self.cells.setdefault(p, []).append(("food", p))
        living = [c for c in self.citizens.values() if c["alive"]]
        wealth = [c["money"] for c in living]
        bonds = [r["trust"] for c in living for r in c["relationships"]]
        average = f"{sum(bonds) / len(bonds):.1f}" if bonds else "unknown"
        self.stats = [f"Living: {len(living)} / {len(self.citizens)}",
                      f"Stored food: {sum(c['food'] for c in living)}",
                      f"Wild food: {sum(self.food.values())}",
                      f"Hungry (12+): {sum(c['hunger'] >= 12 for c in living)}",
                      f"Sleeping: {sum(c['sleeping'] for c in living)}",
                      f"Tired (80+): {sum(c['fatigue'] >= 80 for c in living)}",
                      f"Coins circulating: {sum(c['money'] for c in living)}",
                      f"Coin holdings: {min(wealth, default=0)}..{max(wealth, default=0)}",
                      f"Mean personal trust: {average}",
                      f"Trades: {self.trade_count}",
                      f"Corpses: {len(self.corpses)}",
                      f"Available bodies: {sum(not c['buried'] and not c['reanimated'] and c['decay'] < c['decay_hours'] for c in self.corpses.values())}",
                      f"Occupied graves: {sum(g['occupied'] for g in self.graves.values())}",
                      f"Undead: {len(self.undead)} ({sum(u['active'] for u in self.undead.values())} active)",
                      f"Mana: {sum(c['mana'] for c in living)}",
                      f"Ore mined: {sum(m['initial'] - m['remaining'] for m in self.mines.values())}",
                      f"Ore held: {sum(c['ore'] for c in self.citizens.values()) + sum(u['ore'] for u in self.undead.values())}",
                      f"Ore on ground: {sum(self.ground_ore.values())}",
                      f"Ore exported: {self.snapshot['total_exports']}",
                      f"Food imported: {self.snapshot['total_imports']}"]
        e = self.snapshot["economy"]
        r = e["rates"]
        self.stats += [f"Flow window: {e['window_hours']}h (rates per day)",
                       f"Food produced: {r.get('food_produced', 0):.1f}/day",
                       f"Food consumed: {r.get('food_consumed', 0):.1f}/day",
                       f"Food imports: {r.get('food_imported', 0):.1f}/day",
                       f"Food net: {r['food_balance']:+.1f}/day",
                       f"Ore extracted: {r.get('ore_mined', 0):.1f}/day",
                       f"Mana animation: {r.get('mana_animation', 0):.1f}/day",
                       f"Mana upkeep: {r.get('mana_upkeep', 0):.1f}/day",
                       f"Wealth Gini: {e['wealth_gini']:.3f}"]

    def toggle_pause(self):
        self.paused = not self.paused
        self.credit = 0.0

    def step(self):
        if self.paused:
            self.world.step()
            self.refresh()

    def update(self, elapsed, budget=0.008):
        if self.paused:
            return 0
        self.credit = min(8.0, self.credit + min(max(elapsed, 0), 0.25) * self.SPEEDS[self.speed])
        start, steps = time.perf_counter(), 0
        while self.credit >= 1 and steps < 8 and time.perf_counter() - start < budget:
            self.world.step()
            self.credit -= 1
            steps += 1
        if steps:
            self.refresh()
        return steps

    def inspect(self, selection):
        if selection is None:
            return None
        kind, identifier = selection
        if kind == "event":
            return self.event(identifier)
        if kind == "citizen":
            return deepcopy(self.citizens.get(identifier))
        if kind == "corpse":
            return deepcopy(self.corpses.get(identifier))
        if kind == "grave":
            return deepcopy(self.graves.get(identifier))
        if kind == "undead":
            return deepcopy(self.undead.get(identifier))
        if kind == "mine":
            return deepcopy(self.mines.get(identifier))
        if kind == "ore":
            return dict(x=identifier[0], y=identifier[1], ore=self.ground_ore.get(identifier, 0))
        return dict(x=identifier[0], y=identifier[1], food=self.food.get(identifier, 0))

    def event(self, index):
        return deepcopy(self.world.events[index])


@dataclass
class Camera:
    x: float = 0
    y: float = 0
    cell: float = 28

    def screen_to_world(self, position, origin=(0, 0)):
        return ((position[0] - origin[0]) / self.cell + self.x,
                (position[1] - origin[1]) / self.cell + self.y)

    def tile(self, position, origin=(0, 0)):
        x, y = self.screen_to_world(position, origin)
        return math.floor(x), math.floor(y)

    def screen(self, tile, origin=(0, 0)):
        return (origin[0] + (tile[0] - self.x) * self.cell,
                origin[1] + (tile[1] - self.y) * self.cell)

    def zoom(self, factor, anchor, origin=(0, 0)):
        before = self.screen_to_world(anchor, origin)
        self.cell = min(72, max(12, self.cell * factor))
        self.x = before[0] - (anchor[0] - origin[0]) / self.cell
        self.y = before[1] - (anchor[1] - origin[1]) / self.cell

    def center(self, tile, size):
        self.x = tile[0] + 0.5 - size[0] / (2 * self.cell)
        self.y = tile[1] + 0.5 - size[1] / (2 * self.cell)
