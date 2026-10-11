"""Deterministic hourly simulation; citizens perceive within three tiles."""

from dataclasses import asdict, dataclass
import random

from . import __version__
from .names import generate_names


@dataclass(frozen=True)
class Config:
    seed: int = 1
    citizens: int = 20
    width: int = 32
    height: int = 14
    patches: int = 65

    def __post_init__(self):
        if self.width < 2 or self.height < 2:
            raise ValueError("map dimensions must be at least 2")
        if not 1 <= self.citizens <= self.width * self.height:
            raise ValueError("citizens must fit on the map")
        if not 0 <= self.patches <= self.width * self.height:
            raise ValueError("food patches must fit on the map")


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

    @property
    def capacity(self):
        return {"forager": 4, "farmer": 8, "merchant": 12}[self.occupation]

    @property
    def asking_price(self):
        return {"farmer": 1, "forager": 2, "merchant": 3}[self.occupation]


class World:
    def __init__(self, config=Config()):
        self.config = config
        self.rng = random.Random(config.seed)
        self.tick = 0
        cells = [(x, y) for y in range(config.height) for x in range(config.width)]
        self.food = {p: self.rng.randint(2, 6)
                     for p in self.rng.sample(cells, config.patches)}
        self.patches = set(self.food)
        self.citizens = [Citizen(i + 1, *p) for i, p in
                         enumerate(self.rng.sample(cells, config.citizens))]
        occupations = ["farmer", "forager", "forager", "merchant"]
        for c, name in zip(self.citizens, generate_names(config.seed, config.citizens)):
            c.occupation = occupations[(c.id - 1) % len(occupations)]
            c.name = name
        self.events = []

    def distance(self, c, position):
        return abs(position[0] - c.x) + abs(position[1] - c.y)

    def sellers(self, buyer):
        # Only nearby living inhabitants with a personal reserve offer food.
        limit = 8 if buyer.occupation == "merchant" else 2
        willingness = 2 if buyer.occupation == "merchant" else (3 if buyer.hunger >= 12 else 1)
        if buyer.food >= limit:
            return []
        return sorted((c for c in self.citizens if c.id != buyer.id and c.alive
                       and c.food > 2 and c.hunger < 12
                       and c.asking_price <= min(buyer.money, willingness)
                       and self.distance(buyer, (c.x, c.y)) <= 3),
                      key=lambda c: (c.asking_price, self.distance(buyer, (c.x, c.y)), c.id))

    def trade(self, buyer, seller):
        price = seller.asking_price
        buyer.money -= price
        seller.money += price
        seller.food -= 1
        buyer.food += 1
        self.emit("trade", buyer.id, seller=seller.id, amount=1, price=price)

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
            visible = [p for p, amount in self.food.items()
                       if (amount > 0 or (c.occupation == "farmer" and p in self.patches))
                       and self.distance(c, p) <= 3]
            if offers:
                self.move(c, (offers[0].x, offers[0].y))
            elif visible and c.food < c.capacity:
                self.move(c, min(visible, key=lambda p: (self.distance(c, p), p[1], p[0])))
            elif c.occupation == "farmer" and here in self.patches:
                self.emit("rest", c.id)
            else:
                self.move(c)

    def emit(self, kind, citizen=None, **details):
        self.events.append(dict(tick=self.tick, kind=kind,
                                citizen=citizen, **details))

    def step(self):
        self.tick += 1
        # Fixed ID order resolves competition for food; occupancy does not block movement.
        for c in self.citizens:
            if not c.alive:
                continue
            c.hunger += 1
            if c.hunger >= 6 and c.food:
                c.food -= 1
                c.hunger = max(0, c.hunger - 6)
                self.emit("eat", c.id, food=c.food, hunger=c.hunger)
                continue
            self.act(c)
            if c.hunger >= 48:
                c.alive = False
                dropped = c.food
                self.food[(c.x, c.y)] = self.food.get((c.x, c.y), 0) + dropped
                c.food = 0
                self.emit("starve", c.id, x=c.x, y=c.y, dropped=dropped)
        # Existing patches replenish daily, each with an explicit resource event.
        if self.tick % 24 == 0:
            for p in sorted(self.patches):
                if self.food[p] < 6:
                    self.food[p] += 1
                    self.emit("grow", x=p[0], y=p[1], amount=1)

    def state(self):
        return dict(tick=self.tick, citizens=[asdict(c) for c in self.citizens],
                    food=[[x, y, amount] for (x, y), amount in sorted(self.food.items())])

    def record(self):
        return dict(version=__version__, config=asdict(self.config),
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
    return world
