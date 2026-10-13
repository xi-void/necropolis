"""Passive economic measurements. No decisions, random draws, or resource mutations."""

from collections import Counter, deque
from copy import deepcopy


def event_flows(event):
    kind = event["kind"]
    if kind in ("produce", "grow"):
        return {"food_produced": event.get("amount", 1)}
    if kind == "eat":
        return {"food_consumed": 1}
    if kind == "ore_export":
        return {"food_imported": event["food_imported"], "ore_exported": event["ore"]}
    if kind == "mine_ore":
        source = "ore_undead" if event.get("undead") is not None else "ore_living"
        return {"ore_mined": event["amount"], source: event["amount"]}
    if kind in ("trade", "trade_ore"):
        return {"trades": 1}
    if kind == "mana_replenished":
        return {"mana_replenished": event["amount"]}
    if kind == "animate":
        return {"mana_animation": event["cost"]}
    if kind == "mana_upkeep":
        return {"mana_upkeep": event["amount"]}
    if kind in ("starve", "death"):
        return {"deaths": 1, "starvation": int(kind == "starve")}
    return {}


def gini(values):
    ordered = sorted(values)
    total, n = sum(ordered), len(ordered)
    if total == 0 or n == 0:
        return 0.0
    return sum((2 * i - n - 1) * v for i, v in enumerate(ordered, 1)) / (n * total)


class Economy:
    def __init__(self):
        self.buckets = deque()
        self.totals = Counter()
        self.history = []

    def advance(self, tick):
        if not self.buckets or self.buckets[-1][0] != tick:
            self.buckets.append((tick, Counter()))
        while self.buckets and self.buckets[0][0] <= tick - 24:
            self.buckets.popleft()

    def consume(self, event):
        flows = event_flows(event)
        if flows:
            self.advance(event["tick"])
            self.buckets[-1][1].update(flows)
            self.totals.update(flows)

    def current(self, world):
        living = [c for c in world.citizens if c.alive]
        wealth = [c.money for c in living]
        counts = Counter()
        for _, bucket in self.buckets:
            counts.update(bucket)
        hours = min(24, world.tick)
        rates = {key: amount * 24 / hours if hours else 0.0 for key, amount in counts.items()}
        rates["food_balance"] = rates.get("food_produced", 0) + rates.get("food_imported", 0) - rates.get("food_consumed", 0)
        return dict(tick=world.tick, window_hours=hours, flows=dict(counts), rates=rates,
                    totals=dict(self.totals), living=len(living), undead=len(world.undead),
                    active_undead=sum(u.active for u in world.undead),
                    food=sum(world.food.values()) + sum(c.food for c in living),
                    stored_food=sum(c.food for c in living),
                    ore=sum(c.ore for c in world.citizens) + sum(u.ore for u in world.undead) + sum(world.ground_ore.values()),
                    ore_remaining=sum(m.remaining for m in world.mines),
                    mana=sum(c.mana for c in living), wealth_gini=gini(wealth),
                    wealth=[dict(id=c.id, coins=c.money) for c in living],
                    occupations=dict(Counter(c.occupation for c in living)),
                    export_slots=max(0, world.config.daily_ore_exports - world.exports_today))

    def sample(self, world):
        self.history.append(deepcopy(self.current(world)))


def worker_status(worker, citizens, mines, tick):
    """Observed conditions, not an invented agent decision or knowledge source."""
    keeper = citizens[worker["keeper_id"]]
    distance = abs(worker["x"] - keeper["x"]) + abs(worker["y"] - keeper["y"])
    if not keeper["alive"]:
        return "inactive: keeper deceased"
    if distance > 6:
        return "inactive: outside upkeep range"
    if not worker["active"]:
        return "inactive: keeper lacks mana" if keeper["mana"] < 1 else "inactive: awaiting magical upkeep"
    if worker["ore"] >= 4 or (worker["mine_id"] is None and worker["ore"]):
        if distance > 1:
            return "delivering ore"
        if keeper["ore"] >= 8:
            return "blocked: keeper ore storage full"
        return "ready to deliver ore"
    mine = mines.get(worker["mine_id"])
    if mine is None:
        return "idle: awaiting mine assignment"
    if (worker["x"], worker["y"]) != (mine["x"], mine["y"]):
        return "travelling to mine"
    if not mine["remaining"]:
        return "idle: deposit exhausted"
    return "mining"


def history_lines(history):
    lines = ["Hour  Living  Food  Ore held  Mana  Wealth Gini"]
    for row in history[-10:]:
        lines.append(f"{row['tick']:4d}  {row['living']:6d}  {row['food']:4d}  {row['ore']:8d}"
                     f"  {row['mana']:4d}  {row['wealth_gini']:.3f}")
    return lines


def citizen_conditions(c):
    if not c["alive"]:
        return ["deceased"]
    conditions = []
    if c["sleeping"]:
        conditions.append("sleeping")
    if c["food"] < 2:
        conditions.append("low food reserves")
    if c["money"] == 0:
        conditions.append("no coins for purchases")
    if c["ore"] >= 8:
        conditions.append("ore storage full")
    if c["occupation"] == "necromancer" and c["mana"] < 30:
        conditions.append("mana below animation cost")
    return conditions
