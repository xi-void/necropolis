# NECROPOLIS

A small artificial settlement. Twenty autonomous farmers, foragers, and merchants find food and trade while you observe. Python 3.10 or newer; no installation or external dependencies required.

From this directory:

```sh
python3 -m necropolis --observe --seed 47
python3 -m necropolis --seed 47 --days 30 --log /tmp/necropolis-47.json
python3 -m necropolis --replay /tmp/necropolis-47.json
python3 -m necropolis --seed 47 --days 30 --patches 15
python3 -m unittest discover -s tests -v
```

In observation mode, press Enter to advance one hour, `d` to advance one day, `i` to inspect all citizens, and `q` to quit. Add `--log PATH` to save the run when quitting. Batch mode advances `--days` days and prints the final map. `--patches` changes initial food abundance; the default is 65.

## Version 0.2.1 rules

Citizens receive unique, generated given names and family names with a Dunmer/Telvanni-inspired sound. These are original combinations rather than a roster of existing characters. Names appear in inspection and readable event logs; structured events retain stable citizen IDs, with names stored in the citizen state. A separate seeded random stream generates names so naming does not alter economic behavior or movement.

The seeded map contains renewable food patches and 20 citizens, each initially carrying two food units and 12 coins. Occupations repeat in ID order: farmer, forager, forager, merchant (five farmers, ten foragers, five merchants). Each hour adds one hunger point. A citizen with at least six hunger points eats one stored unit, reducing hunger by six. Otherwise, they trade, produce, gather, move, or rest. Food and trade opportunities are visible within Manhattan distance three. Movement, gathering, farming, buying, and eating each take one hour for the acting citizen.

Farmers carry up to eight food units and produce one unit per work hour while standing on an original food patch, including a depleted patch. They stay there when their inventory is full. Foragers carry four units and gather naturally available food. Merchants carry twelve units, buy cheap local surplus until holding eight units, and also gather when possible. Farmers and foragers also buy when holding fewer than two units.

Sellers must be alive, have more than two food units, and have less than 12 hunger points. Asking prices are one coin for farmers, two for foragers, and three for merchants. Merchants pay at most two; others pay at most one unless their hunger reaches 12, when they pay up to three. Buyers select the cheapest affordable visible offer, then distance and seller ID. Within one tile they transfer one food unit and the price in coins; otherwise they approach the seller. Trading has priority over production and gathering. Sales are passive for the seller and can occur several times per hour while surplus remains. Prices and occupations are simple fixed rules, not a market-clearing economy.

At 48 hunger points a citizen dies. Stored food is returned to their location; their coins stay with them and leave circulation until inheritance is implemented. Every 24 hours, original food patches below six units replenish by one. Dropped food does not create new renewable patches. Citizens can share tiles. Competition resolves in stable citizen ID order, which gives earlier IDs an advantage.

The display reports living population, stored and wild food, hungry citizens (at least 12 hunger points), total trades, and coins held by living citizens. The map shows `F` farmers, `M` merchants, `@` foragers, `&` crowds, `"` food, `+` remains on empty ground, and `.` ground. Recent eating, gathering, production, trading, and starvation events appear beneath it. Inspection includes occupations and money. All events, including movement, growth, and resting, remain in the full log.

## Reproduction and persistence

JSON records contain the simulation version, seed, configuration, every structured event, and final state. Replay re-runs the recorded number of hours from the initial configuration and checks both the complete event sequence and final state. This requires the same simulation version and a compatible Python random implementation. Records persist history and verify reproduction; loading a saved run for continued simulation is not yet implemented.

Logs from earlier versions are incompatible with version 0.2.1 and are rejected explicitly. There is no social memory, disease, or direct citizen control in this milestone. Later mechanics follow the roadmap in [AGENTS.md](AGENTS.md). Outcomes arise from resource availability and local decisions.
