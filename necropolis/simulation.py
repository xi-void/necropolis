"""Deterministic hourly simulation; citizens perceive within three tiles."""

from dataclasses import asdict, dataclass, field
import random

from . import __version__
from .names import generate_names
from .economy import Economy


@dataclass(frozen=True)
class Config:
    seed: int = 1
    citizens: int = 20
    width: int = 32
    height: int = 14
    patches: int = 65
    initial_trust: int = 50
    corpse_decay_hours: int = 168
    grave_count: int = 4
    necromancy: bool = True
    mine_count: int = 3
    ore_per_mine: int = 120
    daily_ore_exports: int = 8

    def __post_init__(self):
        if not 0 <= self.mine_count <= self.width * self.height:
            raise ValueError("mines must fit on the map")
        if self.ore_per_mine < 1 or self.daily_ore_exports < 0:
            raise ValueError("ore per mine must be positive and daily exports nonnegative")
        if not 0 <= self.grave_count <= min(3, self.width) * min(3, self.height):
            raise ValueError("grave count must fit the map and be between 0 and 9")
        if self.corpse_decay_hours < 1:
            raise ValueError("corpse decay duration must be at least one hour")
        if not 0 <= self.initial_trust <= 100:
            raise ValueError("initial trust must be between 0 and 100")
        if self.width < 2 or self.height < 2:
            raise ValueError("map dimensions must be at least 2")
        if not 1 <= self.citizens <= self.width * self.height:
            raise ValueError("citizens must fit on the map")
        if not 0 <= self.patches <= self.width * self.height:
            raise ValueError("food patches must fit on the map")


@dataclass
class Corpse:
    id: int
    citizen_id: int | None
    name: str
    x: int
    y: int
    died_at: int | None
    cause: str
    decay_hours: int
    decay: int = 0
    preserved: bool = False
    reanimated: bool = False
    buried: bool = False

    @property
    def available(self):
        """Whether this physical body can be used by a future reanimation system."""
        return not self.buried and not self.reanimated and self.decay < self.decay_hours

    @property
    def stage(self):
        if self.decay >= self.decay_hours:
            return "gone"
        if self.decay * 3 >= self.decay_hours * 2:
            return "skeletal"
        if self.decay * 3 >= self.decay_hours:
            return "decaying"
        return "fresh"


@dataclass
class Grave:
    id: int
    x: int
    y: int
    corpse_id: int
    occupied: bool = True


@dataclass
class Mine:
    id: int
    x: int
    y: int
    remaining: int
    initial: int


@dataclass
class Undead:
    id: int
    corpse_id: int
    citizen_id: int | None
    name: str
    x: int
    y: int
    keeper_id: int
    next_upkeep: int
    active: bool = True
    integrity: int = 72
    assignment: str = "idle"
    mine_id: int | None = None
    ore: int = 0
    created_at: int = 0

@dataclass
class FoodMemory:
    x: int
    y: int
    amount: int
    patch: bool
    seen: int


@dataclass
class Relationship:
    id: int
    trust: int
    x: int
    y: int
    seen: int
    alive: bool
    surplus: bool
    trades: int = 0
    occupation: str = ""


@dataclass
class Citizen:
    id: int
    x: int
    y: int
    food: int = 2
    hunger: int = 0
    alive: bool = True
    occupation: str = "forager"
    money: int = 12
    name: str = ""
    food_memory: list[FoodMemory] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    memories: list[dict] = field(default_factory=list)
    fatigue: int = 0
    fatigue_rate: int = 4
    recovery_rate: int = 12
    sleeping: bool = False
    corpse_id: int | None = None
    mana: int = 0
    body_memory: list[dict] = field(default_factory=list)
    mine_memory: list[dict] = field(default_factory=list)
    ore: int = 0

    @property
    def capacity(self):
        return {"forager": 4, "farmer": 8, "merchant": 12, "necromancer": 6, "miner": 6}[self.occupation]

    @property
    def asking_price(self):
        return {"farmer": 1, "forager": 2, "merchant": 3, "necromancer": 2, "miner": 2}[self.occupation]


class World:
    def __init__(self, config=Config()):
        self.economy = Economy()
        self.config = config
        self.rng = random.Random(config.seed)
        self.tick = 0
        cells = [(x, y) for y in range(config.height) for x in range(config.width)]
        self.food = {p: self.rng.randint(2, 6)
                     for p in self.rng.sample(cells, config.patches)}
        self.patches = set(self.food)
        self.citizens = [Citizen(i + 1, *p) for i, p in
                         enumerate(self.rng.sample(cells, config.citizens))]
        self.citizens_by_id = {c.id: c for c in self.citizens}
        self.corpses = []
        self.graves = []
        self.undead = []
        self.mines = []
        self.ground_ore = {}
        self.exports_today = 0
        self.total_exports = 0
        self.total_imports = 0
        self.next_entity_id = config.citizens + 1
        occupations = ["farmer", "forager", "forager", "merchant"]
        sleep_rng = random.Random(f"necropolis-sleep-v1:{config.seed}")
        for c, name in zip(self.citizens, generate_names(config.seed, config.citizens)):
            c.occupation = occupations[(c.id - 1) % len(occupations)]
            c.name = name
            c.fatigue_rate = sleep_rng.randint(3, 5)
            c.recovery_rate = sleep_rng.randint(10, 14)
            c.fatigue = sleep_rng.randint(0, 40)
        self.events = []
        candidates = [c for c in self.citizens if c.occupation == "forager"]
        keeper = candidates[-1] if candidates else self.citizens[-1]
        if config.necromancy:
            keeper.occupation = "necromancer"
            keeper.mana = 30
        self.create_graveyard((keeper.x, keeper.y))
        if config.mine_count:
            miners = [c for c in self.citizens if c.occupation == "forager"]
            if miners:
                miners[0].occupation = "miner"
            mine_rng = random.Random(f"necropolis-mines-v1:{config.seed}")
            # First deposit is near the graveyard; additional deposits stay seeded and finite.
            first = (max(0, min(config.width - 1, keeper.x + 2)), keeper.y)
            sites = [first]
            if config.mine_count > 1:
                anchor = candidates[0] if candidates else self.citizens[0]
                second = (min(config.width - 1, anchor.x + 1), anchor.y)
                if second != first:
                    sites.append(second)
            sites += mine_rng.sample([p for p in cells if p not in sites], config.mine_count - len(sites))
            for x, y in sites:
                self.mines.append(Mine(self.allocate_id(), x, y, config.ore_per_mine, config.ore_per_mine))
        self.mines_by_id = {m.id: m for m in self.mines}
        self.economy.sample(self)

    def allocate_id(self):
        identifier = self.next_entity_id
        self.next_entity_id += 1
        return identifier

    def create_graveyard(self, anchor):
        rng = random.Random(f"necropolis-graves-v1:{self.config.seed}")
        width = min(3, self.config.width)
        height = min(3, self.config.height)
        # A small settlement graveyard near the same initial citizen in both comparisons.
        x0 = max(0, min(self.config.width - width, anchor[0] - rng.randrange(width)))
        y0 = max(0, min(self.config.height - height, anchor[1] - rng.randrange(height)))
        sites = rng.sample([(x0 + x, y0 + y) for y in range(height) for x in range(width)],
                           self.config.grave_count)
        for name, (x, y) in zip(generate_names(f"ancestors:{self.config.seed}", len(sites)), sites):
            corpse = Corpse(self.allocate_id(), None, name, x, y, None, "unknown (old grave)",
                            self.config.corpse_decay_hours, preserved=True, buried=True)
            grave = Grave(self.allocate_id(), x, y, corpse.id)
            self.corpses.append(corpse)
            self.graves.append(grave)
            self.emit("grave_created", grave=grave.id, corpse=corpse.id, name=name, x=x, y=y)

    def distance(self, c, position):
        return abs(position[0] - c.x) + abs(position[1] - c.y)

    def relationship(self, c, other):
        return next((r for r in c.relationships if r.id == other.id), None)

    def trust(self, c, other):
        relationship = self.relationship(c, other)
        return relationship.trust if relationship else self.config.initial_trust

    def perceive(self, c):
        c.mine_memory[:] = [m for m in c.mine_memory if self.tick - m["seen"] <= 72
                            and self.distance(c, (m["x"], m["y"])) > 3]
        for mine in self.mines:
            if self.distance(c, (mine.x, mine.y)) <= 3:
                c.mine_memory.append(dict(id=mine.id, x=mine.x, y=mine.y,
                                          remaining=mine.remaining, seen=self.tick))
        c.body_memory[:] = [m for m in c.body_memory
                            if self.tick - m["seen"] <= 72 and self.distance(c, (m["x"], m["y"])) > 3]
        for body in self.corpses:
            if self.distance(c, (body.x, body.y)) <= 3 and not body.reanimated:
                c.body_memory.append(dict(id=body.id, x=body.x, y=body.y, buried=body.buried,
                                          available=body.available, seen=self.tick))
        c.food_memory[:] = [m for m in c.food_memory if self.tick - m.seen <= 72]
        for y in range(max(0, c.y - 3), min(self.config.height, c.y + 4)):
            for x in range(max(0, c.x - 3), min(self.config.width, c.x + 4)):
                if self.distance(c, (x, y)) > 3:
                    continue
                c.food_memory[:] = [m for m in c.food_memory if (m.x, m.y) != (x, y)]
                if (x, y) in self.food:
                    c.food_memory.append(FoodMemory(x, y, self.food[(x, y)],
                                                   (x, y) in self.patches, self.tick))
        for other in self.citizens:
            if other.id == c.id or self.distance(c, (other.x, other.y)) > 3:
                continue
            r = self.relationship(c, other)
            if r is None:
                r = Relationship(other.id, self.config.initial_trust, other.x, other.y,
                                 self.tick, other.alive, other.food > 2)
                c.relationships.append(r)
                c.memories.append(dict(tick=self.tick, kind="encounter", citizen=other.id))
            r.x, r.y, r.seen = other.x, other.y, self.tick
            r.alive = other.alive
            r.occupation = other.occupation
            r.surplus = other.food > 2 and other.hunger < 12 and not other.sleeping
        c.memories[:] = c.memories[-12:]

    def price(self, seller, buyer):
        return max(1, seller.asking_price - (self.trust(seller, buyer) >= 75))

    def sellers(self, buyer):
        # Only nearby living inhabitants with a personal reserve offer food.
        limit = 8 if buyer.occupation == "merchant" else 2
        willingness = 2 if buyer.occupation == "merchant" else (3 if buyer.hunger >= 12 else 1)
        if buyer.food >= limit:
            return []
        return sorted((c for c in self.citizens if c.id != buyer.id and c.alive and not c.sleeping
                       and c.food > 2 and c.hunger < 12
                       and self.price(c, buyer) <= min(buyer.money, willingness)
                       and self.trust(c, buyer) >= 20
                       and (self.trust(buyer, c) >= 20 or buyer.hunger >= 24)
                       and self.distance(buyer, (c.x, c.y)) <= 3),
                      key=lambda c: (self.price(c, buyer), -self.trust(buyer, c),
                                     self.distance(buyer, (c.x, c.y)), c.id))

    def trade(self, buyer, seller):
        if buyer.sleeping or seller.sleeping:
            raise ValueError("sleeping citizens cannot trade")
        price = self.price(seller, buyer)
        buyer.money -= price
        seller.money += price
        seller.food -= 1
        buyer.food += 1
        self.emit("trade", buyer.id, seller=seller.id, amount=1, price=price)
        self.bond_after_trade(buyer, seller)

    def bond_after_trade(self, buyer, seller):
        for c, other in ((buyer, seller), (seller, buyer)):
            r = self.relationship(c, other)
            if r is None:
                r = Relationship(other.id, self.config.initial_trust, other.x, other.y,
                                 self.tick, True, other.food > 2)
                c.relationships.append(r)
            r.trust = min(100, r.trust + 5)
            r.trades += 1
            r.x, r.y, r.seen = other.x, other.y, self.tick

    def move(self, c, target=None):
        if target is None:
            dx, dy = self.rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
        else:
            dx = (target[0] > c.x) - (target[0] < c.x)
            dy = 0 if dx else (target[1] > c.y) - (target[1] < c.y)
        c.x = max(0, min(self.config.width - 1, c.x + dx))
        c.y = max(0, min(self.config.height - 1, c.y + dy))
        self.emit("move", c.id, x=c.x, y=c.y)

    def act(self, c):
        here = (c.x, c.y)
        offers = self.sellers(c)
        if self.economic_action(c):
            return
        if c.occupation == "necromancer" and c.food >= 2 and self.magic_action(c):
            return
        if offers and self.distance(c, (offers[0].x, offers[0].y)) <= 1:
            self.trade(c, offers[0])
        elif c.occupation == "farmer" and here in self.patches and c.food < c.capacity:
            # One hour tending a real food patch produces one new unit.
            c.food += 1
            self.emit("produce", c.id, x=c.x, y=c.y, amount=1)
        elif self.food.get(here, 0) and c.food < c.capacity:
            self.food[here] -= 1
            c.food += 1
            self.emit("gather", c.id, x=c.x, y=c.y, food=c.food)
        else:
            remembered_food = [(m.x, m.y) for m in c.food_memory
                               if m.amount > 0 or (c.occupation == "farmer" and m.patch)]
            remembered_sellers = [r for r in c.relationships if r.alive and r.surplus
                                  and r.trust >= 20 and self.tick - r.seen <= 24
                                  and self.distance(c, (r.x, r.y)) > 3]
            if offers:
                self.move(c, (offers[0].x, offers[0].y))
            elif remembered_food and c.food < c.capacity:
                self.move(c, min(remembered_food, key=lambda p: (self.distance(c, p), p[1], p[0])))
            elif remembered_sellers and c.food < 2 and c.money:
                r = min(remembered_sellers, key=lambda r: (-r.trust, self.distance(c, (r.x, r.y)), r.id))
                self.move(c, (r.x, r.y))
            elif c.occupation == "farmer" and here in self.patches:
                self.emit("rest", c.id)
            else:
                self.move(c)

    def ore_sellers(self, buyer):
        return sorted((c for c in self.citizens if c.id != buyer.id and c.alive and not c.sleeping
                       and c.ore > 0 and self.distance(buyer, (c.x, c.y)) <= 3
                       and self.trust(buyer, c) >= 20 and self.trust(c, buyer) >= 20),
                      key=lambda c: (self.distance(buyer, (c.x, c.y)), c.id))

    def trade_ore(self, buyer, seller):
        if (not buyer.alive or buyer.sleeping or buyer.occupation != "merchant" or buyer.money < 1
                or buyer.ore >= 8 or not seller.alive or seller.sleeping or seller.ore < 1
                or self.distance(buyer, (seller.x, seller.y)) > 1
                or self.trust(buyer, seller) < 20 or self.trust(seller, buyer) < 20):
            raise ValueError("ore trade requires a local affordable trusted offer")
        seller.ore -= 1
        buyer.ore += 1
        buyer.money -= 1
        seller.money += 1
        self.emit("trade_ore", buyer.id, seller=seller.id, amount=1, price=1)
        self.bond_after_trade(buyer, seller)

    def export_ore(self, c):
        if (not c.alive or c.sleeping or c.occupation != "merchant" or c.ore < 1
                or c.food + 2 > c.capacity or self.exports_today >= self.config.daily_ore_exports):
            raise ValueError("external exchange requires ore, storage and remaining daily quota")
        c.ore -= 1
        c.food += 2
        self.exports_today += 1
        self.total_exports += 1
        self.total_imports += 2
        self.emit("ore_export", c.id, ore=1, food_imported=2)

    def extract(self, miner, mine, citizen_id, undead_id=None):
        if isinstance(miner, Citizen) and (not miner.alive or miner.sleeping or miner.occupation != "miner"):
            raise ValueError("living extraction requires an awake miner")
        if isinstance(miner, Undead) and not miner.active:
            raise ValueError("inactive undead cannot extract ore")
        if (mine.remaining <= 0 or miner.ore >= 8
                or self.distance(miner, (mine.x, mine.y)) != 0):
            raise ValueError("extraction requires a nonempty local mine and ore storage")
        mine.remaining -= 1
        miner.ore += 1
        self.emit("mine_ore", citizen_id, mine=mine.id, amount=1, undead=undead_id)

    def economic_action(self, c):
        here = (c.x, c.y)
        if (c.occupation in ("miner", "merchant", "necromancer") and c.food >= 2 and c.ore < 8
                and self.ground_ore.get(here, 0)):
            self.ground_ore[here] -= 1
            c.ore += 1
            self.emit("ore_collected", c.id, amount=1, x=c.x, y=c.y)
            return True
        if c.occupation == "merchant":
            if c.ore and c.food + 2 <= c.capacity and self.exports_today < self.config.daily_ore_exports:
                self.export_ore(c)
                return True
            if (c.food >= 2 and c.ore < 8 and c.money
                    and self.exports_today < self.config.daily_ore_exports):
                suppliers = self.ore_sellers(c)
                if suppliers:
                    seller = suppliers[0]
                    if self.distance(c, (seller.x, seller.y)) <= 1:
                        self.trade_ore(c, seller)
                    else:
                        self.move(c, (seller.x, seller.y))
                    return True
        if c.occupation in ("miner", "necromancer") and c.ore:
            customers = [r for r in c.relationships if r.alive and r.occupation == "merchant"
                         and r.trust >= 20 and self.tick - r.seen <= 24]
            if customers and (c.ore >= 4 or c.food < 2):
                r = min(customers, key=lambda r: (self.distance(c, (r.x, r.y)), r.id))
                if self.distance(c, (r.x, r.y)) > 1:
                    self.move(c, (r.x, r.y))
                    return True
        if c.occupation == "miner" and c.food >= 2 and c.ore < 8:
            known = [m for m in c.mine_memory if m["remaining"] > 0]
            if known:
                target = min(known, key=lambda m: (self.distance(c, (m["x"], m["y"])), m["id"]))
                if self.distance(c, (target["x"], target["y"])):
                    self.move(c, (target["x"], target["y"]))
                else:
                    mine = self.mines_by_id[target["id"]]
                    if mine.remaining:
                        self.extract(c, mine, c.id)
                    else:
                        return False
                return True
        return False

    def magic_action(self, c):
        workers = [u for u in self.undead if u.keeper_id == c.id]
        if c.mana < 30 and (workers or c.body_memory):
            amount = min(6, 60 - c.mana)
            c.mana += amount
            self.emit("mana_replenished", c.id, amount=amount, mana=c.mana)
            return True
        known_mines = [m for m in c.mine_memory if m["remaining"] > 0]
        if self.config.mine_count and self.config.daily_ore_exports == 0:
            return False
        if self.config.mine_count and not known_mines:
            return False
        for worker in workers:
            if worker.mine_id is None and known_mines:
                target = min(known_mines, key=lambda m: (self.distance(worker, (m["x"], m["y"])), m["id"]))
                worker.mine_id = target["id"]
                worker.assignment = "mining"
                self.emit("undead_assigned", c.id, undead=worker.id, mine=worker.mine_id)
                return True
        known = [m for m in c.body_memory if m["buried"] or m["available"]]
        if not known or c.mana < 30:
            return False
        target = min(known, key=lambda m: (self.distance(c, (m["x"], m["y"])), m["id"]))
        if self.distance(c, (target["x"], target["y"])) > 0:
            self.move(c, (target["x"], target["y"]))
            return True
        body = next((b for b in self.corpses if b.id == target["id"]), None)
        if body is None:
            return False
        if body.buried:
            self.exhume(c, body)
        elif body.available:
            self.animate(c, body)
        else:
            return False
        return True

    def exhume(self, c, body):
        if (not c.alive or c.sleeping or c.occupation != "necromancer" or not body.buried
                or not any(b is body for b in self.corpses) or self.distance(c, (body.x, body.y)) != 0):
            raise ValueError("exhumation requires an awake necromancer at an occupied grave")
        grave = next(g for g in self.graves if g.corpse_id == body.id)
        grave.occupied = False
        body.buried = body.preserved = False
        self.emit("exhume", c.id, grave=grave.id, corpse=body.id, name=body.name)

    def animate(self, c, body):
        if (not c.alive or c.sleeping or c.occupation != "necromancer" or c.mana < 30
                or not any(b is body for b in self.corpses) or not body.available
                or self.distance(c, (body.x, body.y)) != 0):
            raise ValueError("animation requires an eligible local body and 30 mana")
        c.mana -= 30
        body.reanimated = True
        worker = Undead(self.allocate_id(), body.id, body.citizen_id, body.name,
                        body.x, body.y, c.id, self.tick + 6, created_at=self.tick)
        known = [m for m in c.mine_memory if m["remaining"] > 0]
        if known and self.config.daily_ore_exports:
            worker.mine_id = min(known, key=lambda m: (self.distance(worker, (m["x"], m["y"])), m["id"]))["id"]
            worker.assignment = "mining"
        self.undead.append(worker)
        self.corpses.remove(body)
        self.emit("animate", c.id, undead=worker.id, corpse=body.id, name=body.name, cost=30)
        self.emit("corpse_removed", body.citizen_id, corpse=body.id, name=body.name,
                  x=body.x, y=body.y, reason="reanimation")

    def maintain_undead(self):
        remaining = []
        for worker in self.undead:
            keeper = self.citizens_by_id[worker.keeper_id]
            linked = keeper.alive and self.distance(keeper, (worker.x, worker.y)) <= 6
            was_active = worker.active
            if not linked:
                worker.active = False
            elif self.tick >= worker.next_upkeep or not worker.active:
                if keeper.mana >= 1:
                    keeper.mana -= 1
                    worker.active = True
                    worker.next_upkeep = self.tick + 6
                    self.emit("mana_upkeep", keeper.id, undead=worker.id, amount=1, mana=keeper.mana)
                else:
                    worker.active = False
            if worker.active != was_active:
                self.emit("undead_active" if worker.active else "undead_inactive", keeper.id,
                          undead=worker.id, reason="maintained" if worker.active else "keeper/range/mana")
            if not worker.active:
                worker.integrity -= 1
            if worker.integrity <= 0:
                if worker.ore:
                    p = (worker.x, worker.y)
                    self.ground_ore[p] = self.ground_ore.get(p, 0) + worker.ore
                self.emit("undead_removed", keeper.id, undead=worker.id, reason="deterioration", ore_dropped=worker.ore)
            else:
                remaining.append(worker)
        self.undead = remaining

    def work_undead(self):
        for worker in self.undead:
            if not worker.active or worker.created_at >= self.tick:
                continue
            keeper = self.citizens_by_id[worker.keeper_id]
            if worker.ore >= 4 or (worker.mine_id is None and worker.ore):
                if self.distance(worker, (keeper.x, keeper.y)) > 1:
                    dx = (keeper.x > worker.x) - (keeper.x < worker.x)
                    dy = 0 if dx else (keeper.y > worker.y) - (keeper.y < worker.y)
                    worker.x += dx
                    worker.y += dy
                    self.emit("undead_move", keeper.id, undead=worker.id, x=worker.x, y=worker.y)
                elif keeper.ore < 8:
                    amount = min(worker.ore, 8 - keeper.ore)
                    worker.ore -= amount
                    keeper.ore += amount
                    self.emit("ore_delivered", keeper.id, undead=worker.id, amount=amount)
                continue
            if worker.mine_id is None:
                continue
            mine = self.mines_by_id[worker.mine_id]
            if self.distance(worker, (mine.x, mine.y)):
                dx = (mine.x > worker.x) - (mine.x < worker.x)
                dy = 0 if dx else (mine.y > worker.y) - (mine.y < worker.y)
                worker.x += dx
                worker.y += dy
                self.emit("undead_move", keeper.id, undead=worker.id, x=worker.x, y=worker.y)
            elif mine.remaining:
                self.extract(worker, mine, keeper.id, worker.id)
            else:
                worker.mine_id = None
                worker.assignment = "idle (deposit exhausted)"
                self.emit("undead_idle", keeper.id, undead=worker.id, reason="deposit exhausted")

    def emit(self, kind, citizen=None, **details):
        event = dict(tick=self.tick, kind=kind, citizen=citizen, **details)
        self.events.append(event)
        self.economy.consume(event)
        if kind in ("trade", "trade_ore", "starve", "death", "exhume", "animate"):
            actor = self.citizens_by_id[citizen]
            for witness in self.citizens:
                if witness.alive and not witness.sleeping and (witness.id in (citizen, details.get("seller"))
                                      or self.distance(witness, (actor.x, actor.y)) <= 3):
                    witness.memories.append(event.copy())
                    witness.memories[:] = witness.memories[-12:]

    def sleep_hour(self, c):
        c.fatigue = max(0, c.fatigue - c.recovery_rate)
        self.emit("sleep", c.id, fatigue=c.fatigue, hunger=c.hunger)
        if c.fatigue <= 10:
            c.sleeping = False
            self.emit("wake", c.id, reason="rested", fatigue=c.fatigue)

    def live_hour(self, c):
        c.hunger += 1
        interrupted = False
        if c.sleeping:
            # Hunger can break sleep; the waking hour is spent eating or seeking food.
            if ((c.hunger >= 12 and c.food) or c.hunger >= 24
                    or (c.food == 0 and c.hunger >= 6 and c.fatigue <= 80)):
                c.sleeping = False
                interrupted = True
                self.emit("wake", c.id, reason="hunger", fatigue=c.fatigue)
            else:
                self.sleep_hour(c)
                return
        self.perceive(c)
        projected_fatigue = min(100, c.fatigue + c.fatigue_rate)
        needs_food = c.food < 2 and c.hunger >= 6
        if c.hunger >= 6 and c.food:
            c.fatigue = projected_fatigue
            c.food -= 1
            c.hunger = max(0, c.hunger - 6)
            self.emit("eat", c.id, food=c.food, hunger=c.hunger)
        elif (not interrupted and projected_fatigue >= 80
              and (not needs_food or projected_fatigue == 100)):
            c.sleeping = True
            self.emit("sleep_start", c.id, fatigue=c.fatigue)
            self.sleep_hour(c)
        else:
            c.fatigue = projected_fatigue
            self.act(c)

    def step(self):
        self.tick += 1
        self.economy.advance(self.tick)
        if self.tick % 24 == 0:
            self.exports_today = 0
        self.decay_corpses()
        # Fixed ID order resolves competition for food; occupancy does not block movement.
        for c in self.citizens:
            if not c.alive:
                continue
            self.live_hour(c)
            if c.hunger >= 48:
                self.die(c, "starvation")
        self.maintain_undead()
        self.work_undead()
        # Existing patches replenish daily, each with an explicit resource event.
        if self.tick % 24 == 0:
            for p in sorted(self.patches):
                if self.food[p] < 6:
                    self.food[p] += 1
                    self.emit("grow", x=p[0], y=p[1], amount=1)
        if self.tick % 24 == 0:
            self.economy.sample(self)

    def die(self, c, cause):
        """Transition once from living citizen to historical identity and physical body."""
        if not c.alive:
            return
        c.alive = False
        c.sleeping = False
        dropped = c.food
        self.food[(c.x, c.y)] = self.food.get((c.x, c.y), 0) + dropped
        c.food = 0
        ore_dropped = c.ore
        if ore_dropped:
            self.ground_ore[(c.x, c.y)] = self.ground_ore.get((c.x, c.y), 0) + ore_dropped
            c.ore = 0
        corpse = Corpse(self.allocate_id(), c.id, c.name, c.x, c.y,
                        self.tick, cause, self.config.corpse_decay_hours)
        c.corpse_id = corpse.id
        self.corpses.append(corpse)
        kind = "starve" if cause == "starvation" else "death"
        self.emit(kind, c.id, x=c.x, y=c.y, dropped=dropped, ore_dropped=ore_dropped,
                  cause=cause, corpse=corpse.id)
        self.emit("corpse_created", c.id, corpse=corpse.id, name=corpse.name,
                  x=corpse.x, y=corpse.y, cause=cause, decay_hours=corpse.decay_hours)

    def decay_corpses(self):
        # Bodies age from the hour AFTER death, even when no citizens remain alive.
        remaining = []
        for corpse in self.corpses:
            if not corpse.preserved and not corpse.reanimated:
                previous = corpse.stage
                corpse.decay = min(corpse.decay_hours, corpse.decay + 1)
                if corpse.stage == "gone":
                    self.emit("corpse_removed", corpse.citizen_id, corpse=corpse.id,
                              name=corpse.name, x=corpse.x, y=corpse.y, reason="decay")
                    continue
                if corpse.stage != previous:
                    self.emit("corpse_decay", corpse.citizen_id, corpse=corpse.id,
                              stage=corpse.stage, decay=corpse.decay)
            remaining.append(corpse)
        self.corpses = remaining

    def state(self):
        return dict(tick=self.tick, citizens=[asdict(c) for c in self.citizens],
                    corpses=[asdict(c) for c in self.corpses],
                    graves=[asdict(g) for g in self.graves],
                    undead=[asdict(u) for u in self.undead],
                    mines=[asdict(m) for m in self.mines],
                    ground_ore=[[x, y, amount] for (x, y), amount in sorted(self.ground_ore.items())],
                    exports_today=self.exports_today, total_exports=self.total_exports,
                    total_imports=self.total_imports,
                    economy=self.economy.current(self),
                    next_entity_id=self.next_entity_id,
                    food=[[x, y, amount] for (x, y), amount in sorted(self.food.items())])

    def record(self):
        return dict(version=__version__, config=asdict(self.config),
                    economy_history=self.economy.history,
                    events=self.events, state=self.state())


def replay(record):
    """Re-run from recorded initial configuration and verify every event and final state."""
    if record["version"] != __version__:
        raise ValueError("replay requires the recorded simulation version")
    world = World(Config(**record["config"]))
    for _ in range(record["state"]["tick"]):
        world.step()
    if world.events != record["events"] or world.state() != record["state"]:
        raise ValueError("replay diverged: event log or final state differs")
    if world.economy.history != record["economy_history"]:
        raise ValueError("replay diverged: economic history differs")
    return world
