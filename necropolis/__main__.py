import argparse
import json
from pathlib import Path

from .simulation import Config, World, replay
from .economy import history_lines, worker_status


def render(world):
    grid = [["." for _ in range(world.config.width)] for _ in range(world.config.height)]
    for (x, y), amount in world.food.items():
        if amount:
            grid[y][x] = '"'
    for mine in world.mines:
        grid[mine.y][mine.x] = "^" if mine.remaining else "v"
    for (x, y), amount in world.ground_ore.items():
        if amount:
            grid[y][x] = "*"
    for corpse in world.corpses:
        if not corpse.reanimated and not corpse.buried:
            grid[corpse.y][corpse.x] = "+"
    for grave in world.graves:
        if grid[grave.y][grave.x] != "+":
            grid[grave.y][grave.x] = "T" if grave.occupied else "_"
    for undead in world.undead:
        grid[undead.y][undead.x] = "U" if undead.active else "u"
    occupied = set()
    for c in world.citizens:
        if c.alive:
            p = (c.x, c.y)
            symbol = "z" if c.sleeping else {"farmer": "F", "merchant": "M", "forager": "@", "necromancer": "N", "miner": "P"}[c.occupation]
            grid[c.y][c.x] = "&" if p in occupied else symbol
            occupied.add(p)
    living = [c for c in world.citizens if c.alive]
    print(f"NECROPOLIS // DAY {world.tick // 24 + 1:04d}  {world.tick % 24:02d}:00"
          f" // SEED {world.config.seed}")
    print("+" + "-" * world.config.width + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * world.config.width + "+")
    print(f"Living {len(living)}/{len(world.citizens)} | Stored food {sum(c.food for c in living)}"
          f" | Wild food {sum(world.food.values())} | Hungry {sum(c.hunger >= 12 for c in living)}")
    trades = [e for e in world.events if e["kind"] in ("trade", "trade_ore")]
    print(f"Trades {len(trades)} | Coins in circulation {sum(c.money for c in living)}")
    bonds = [r.trust for c in living for r in c.relationships]
    average = f"{sum(bonds) / len(bonds):.1f}" if bonds else "unknown"
    wealth = [c.money for c in living]
    print(f"Mean personal trust {average} | Coin holdings {min(wealth, default=0)}..{max(wealth, default=0)}")
    print(f"Sleeping {sum(c.sleeping for c in living)} | Tired {sum(c.fatigue >= 80 for c in living)}")
    print(f"Corpses {sum(not c.reanimated for c in world.corpses)}"
          f" | Available bodies {sum(c.available for c in world.corpses)}")
    print(f"Occupied graves {sum(g.occupied for g in world.graves)}"
          f" | Undead {len(world.undead)} ({sum(u.active for u in world.undead)} active)"
          f" | Mana {sum(c.mana for c in living)}")
    print(f"Ore mined {sum(m.initial - m.remaining for m in world.mines)}"
          f" | Exported {world.total_exports} | Food imported {world.total_imports}")
    e = world.economy.current(world)
    r = e["rates"]
    print(f"Economy /day over {e['window_hours']}h: food produced {r.get('food_produced', 0):.1f}"
          f" consumed {r.get('food_consumed', 0):.1f} imported {r.get('food_imported', 0):.1f}"
          f" net {r['food_balance']:+.1f} | Wealth Gini {e['wealth_gini']:.3f}")
    print('F farmer M merchant @ forager N necromancer P miner U/u undead ^/v mine * ore T/_ grave z sleeping')
    identities = {c.id: f"{c.name} (#{c.id:02d})" for c in world.citizens}
    for event in [e for e in world.events if e["kind"] not in ("move", "grow", "rest", "sleep")][-8:]:
        who = identities[event["citizen"]] if event["citizen"] else "World"
        goods = "ore" if event["kind"] == "trade_ore" else "food"
        detail = (f" bought {goods} from {identities[event['seller']]} for {event['price']} coins"
                  if event["kind"] in ("trade", "trade_ore") else f": {event['kind']}")
        if event["kind"] == "wake":
            detail += f" ({event['reason']})"
        elif event["kind"] == "corpse_created":
            detail += f" body #{event['corpse']} ({event['cause']})"
        elif event["kind"] == "corpse_decay":
            detail += f" body #{event['corpse']} -> {event['stage']}"
        elif event["kind"] == "corpse_removed":
            detail += f" body #{event['corpse']} ({event['reason']})"
        print(f"D{event['tick'] // 24 + 1:04d} {event['tick'] % 24:02d}:00  {who}{detail}")


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def inspect(world):
    identities = {c.id: c.name for c in world.citizens}
    for c in world.citizens:
        print(f"#{c.id:02d} {c.name} | {c.occupation} ({c.x},{c.y}) food={c.food} money={c.money} ore={c.ore} hunger={c.hunger} alive={c.alive}")
        if c.corpse_id is not None:
            print(f"  Historical body ID: #{c.corpse_id}")
        print(f"  Sleep: {'asleep' if c.sleeping else 'awake'} | fatigue={c.fatigue}/100"
              f" awake +{c.fatigue_rate}/h asleep -{c.recovery_rate}/h")
        if c.occupation == "necromancer":
            print(f"  Mana {c.mana}/60 | Known bodies {len(c.body_memory)}")
        print("  Food knowledge: " + (", ".join(
            f"({m.x},{m.y}) food={m.amount} age={world.tick - m.seen}h"
            for m in c.food_memory if m.amount or m.patch) or "none"))
        print("  Relationships: " + (", ".join(
            f"{identities[r.id]} trust={r.trust} trades={r.trades} last=({r.x},{r.y}) {world.tick - r.seen}h ago"
            for r in c.relationships) or "none"))
        for m in c.memories[-4:]:
            print(f"  Remembered at hour {m['tick']}: {m['kind']} / {identities[m['citizen']]}")
    print("CORPSES // " + str(len(world.corpses)))
    for corpse in world.corpses:
        death_time = "unknown" if corpse.died_at is None else f"hour {corpse.died_at}"
        print(f"  Body #{corpse.id}: {corpse.name} (former citizen {corpse.citizen_id if corpse.citizen_id is not None else 'unknown'})"
              f" at ({corpse.x},{corpse.y}) died {death_time} / {corpse.cause}")
        print(f"    {corpse.stage}: decay={corpse.decay}/{corpse.decay_hours}h"
              f" preserved={corpse.preserved} reanimated={corpse.reanimated} available={corpse.available}")
    for g in world.graves:
        print(f"Grave #{g.id} ({g.x},{g.y}) body=#{g.corpse_id} occupied={g.occupied}")
    for u in world.undead:
        print(f"Undead #{u.id} {u.name} keeper=#{u.keeper_id} active={u.active} integrity={u.integrity} ore={u.ore} mine={u.mine_id} {u.assignment}")
        snapshot = world.state()
        print("  Condition: " + worker_status(vars(u), {c['id']: c for c in snapshot['citizens']},
                                            {m['id']: m for m in snapshot['mines']}, world.tick))
    for mine in world.mines:
        print(f"Mine #{mine.id} ({mine.x},{mine.y}) ore={mine.remaining}/{mine.initial}")


def main():
    parser = argparse.ArgumentParser(description="Observe a seeded autonomous settlement.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--days", type=nonnegative, default=30)
    parser.add_argument("--patches", type=nonnegative, default=65)
    parser.add_argument("--initial-trust", type=int, default=50, help="starting trust, 0 to 100")
    parser.add_argument("--corpse-decay-hours", type=int, default=168,
                        help="hours before an unpreserved body disappears (default: 168)")
    parser.add_argument("--graves", type=int, default=4, help="finite initial graves, 0 to 9")
    parser.add_argument("--no-necromancy", action="store_true", help="keep original occupations for comparisons")
    parser.add_argument("--mines", type=int, default=3, help="number of finite ore deposits")
    parser.add_argument("--ore-per-mine", type=int, default=120)
    parser.add_argument("--daily-ore-exports", type=int, default=8, help="settlement-wide ore export quota")
    parser.add_argument("--observe", action="store_true", help="advance interactively")
    parser.add_argument("--gui", action="store_true", help="open the pygame-ce graphical observer")
    parser.add_argument("--ui-scale", type=float, default=1.0, help="GUI text scale (0.75 to 2; e.g. 1.5)")
    parser.add_argument("--log", type=Path, help="save replayable JSON record")
    parser.add_argument("--replay", type=Path, help="verify and display a saved run")
    args = parser.parse_args()
    if args.gui and args.observe:
        parser.error("choose --gui or --observe")
    if not 0.75 <= args.ui_scale <= 2:
        parser.error("--ui-scale must be between 0.75 and 2")
    try:
        if args.gui:
            try:
                from .gui import run
            except ModuleNotFoundError as error:
                if error.name != "pygame":
                    raise
                parser.exit(2, "GUI requires pygame-ce: python3 -m pip install -r requirements-gui.txt\n")
        if args.replay:
            world = replay(json.loads(args.replay.read_text()))
            print("Replay verified.")
        else:
            world = World(Config(seed=args.seed, patches=args.patches,
                                 initial_trust=args.initial_trust,
                                 grave_count=args.graves, necromancy=not args.no_necromancy,
                                 mine_count=args.mines, ore_per_mine=args.ore_per_mine,
                                 daily_ore_exports=args.daily_ore_exports,
                                 corpse_decay_hours=args.corpse_decay_hours))
            if args.gui:
                run(world, scale=args.ui_scale)
            elif args.observe:
                while True:
                    render(world)
                    command = input("[Enter] hour | d day | i inspect | e economy | q quit > ").strip().lower()
                    if command == "q":
                        break
                    if command == "i":
                        inspect(world)
                    elif command == "e":
                        print("\n".join(history_lines(world.economy.history)))
                    elif command in ("", "d"):
                        for _ in range(24 if command == "d" else 1):
                            world.step()
            else:
                for _ in range(args.days * 24):
                    world.step()
        if args.replay and args.gui:
            run(world, scale=args.ui_scale)
        if not args.gui:
            render(world)
        if args.log:
            args.log.write_text(json.dumps(world.record(), indent=2) + "\n")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"necropolis: {error}\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(0, "\nObservation ended.\n")


if __name__ == "__main__":
    main()
