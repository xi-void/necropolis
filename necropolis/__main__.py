import argparse
import json
from pathlib import Path

from .simulation import Config, World, replay


def render(world):
    grid = [["." for _ in range(world.config.width)] for _ in range(world.config.height)]
    for (x, y), amount in world.food.items():
        if amount:
            grid[y][x] = '"'
    occupied = set()
    for c in world.citizens:
        if c.alive:
            p = (c.x, c.y)
            grid[c.y][c.x] = "&" if p in occupied else {"farmer": "F", "merchant": "M", "forager": "@"}[c.occupation]
            occupied.add(p)
        elif grid[c.y][c.x] == ".":
            grid[c.y][c.x] = "+"
    living = [c for c in world.citizens if c.alive]
    print(f"NECROPOLIS // DAY {world.tick // 24 + 1:04d}  {world.tick % 24:02d}:00"
          f" // SEED {world.config.seed}")
    print("+" + "-" * world.config.width + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * world.config.width + "+")
    print(f"Living {len(living)}/{len(world.citizens)} | Stored food {sum(c.food for c in living)}"
          f" | Wild food {sum(world.food.values())} | Hungry {sum(c.hunger >= 12 for c in living)}")
    trades = [e for e in world.events if e["kind"] == "trade"]
    print(f"Trades {len(trades)} | Coins in circulation {sum(c.money for c in living)}")
    print('F farmer  M merchant  @ forager  & crowd  " food  + remains  . ground')
    identities = {c.id: f"{c.name} (#{c.id:02d})" for c in world.citizens}
    for event in [e for e in world.events if e["kind"] not in ("move", "grow", "rest")][-8:]:
        who = identities[event["citizen"]] if event["citizen"] else "World"
        detail = (f" bought food from {identities[event['seller']]} for {event['price']} coins"
                  if event["kind"] == "trade" else f": {event['kind']}")
        print(f"D{event['tick'] // 24 + 1:04d} {event['tick'] % 24:02d}:00  {who}{detail}")


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def main():
    parser = argparse.ArgumentParser(description="Observe a seeded autonomous settlement.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--days", type=nonnegative, default=30)
    parser.add_argument("--patches", type=nonnegative, default=65)
    parser.add_argument("--observe", action="store_true", help="advance interactively")
    parser.add_argument("--log", type=Path, help="save replayable JSON record")
    parser.add_argument("--replay", type=Path, help="verify and display a saved run")
    args = parser.parse_args()
    try:
        if args.replay:
            world = replay(json.loads(args.replay.read_text()))
            print("Replay verified.")
        else:
            world = World(Config(seed=args.seed, patches=args.patches))
            if args.observe:
                while True:
                    render(world)
                    command = input("[Enter] hour | d day | i inspect | q quit > ").strip().lower()
                    if command == "q":
                        break
                    if command == "i":
                        for c in world.citizens:
                            print(f"#{c.id:02d} {c.name} | {c.occupation} ({c.x},{c.y}) food={c.food} money={c.money} hunger={c.hunger} alive={c.alive}")
                    elif command in ("", "d"):
                        for _ in range(24 if command == "d" else 1):
                            world.step()
            else:
                for _ in range(args.days * 24):
                    world.step()
        render(world)
        if args.log:
            args.log.write_text(json.dumps(world.record(), indent=2) + "\n")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"necropolis: {error}\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(0, "\nObservation ended.\n")


if __name__ == "__main__":
    main()
