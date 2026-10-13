# NECROPOLIS

A small artificial settlement. Twenty autonomous citizens find food, trade, sleep, and practice necromancy while you observe. Python 3.10 or newer. CLI and headless modes require no external dependencies; the optional graphical observer uses pygame-ce.

## Graphical observer

Install the single GUI dependency in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-gui.txt
python3 -m necropolis --gui --seed 47
```

The window starts paused. The map shows the existing simulation, with a settlement/inspection sidebar, event history, and time controls. Citizen, corpse, and food inspection uses actual state; age, buildings, crafting, and other unimplemented systems are omitted. Latest action means the most recent emitted action, not a prediction of the citizen's next decision.

Use `--ui-scale 1.5` for larger text on a 1920×1080 display or a scaled desktop. The window is resizable; interface text and map zoom are separate. An existing system monospace font is used when available, with pygame's bundled font as fallback. Follow keeps the selected citizen centered; it retains their identity and corpse link after death. TAB also reaches deceased citizens after physical corpses decay.

| Control | Action |
| --- | --- |
| Space / Pause button | Pause or resume |
| Period / Step button | Advance one hour while paused |
| Right Arrow | Step while paused; pan right while running |
| 1–4 / speed buttons | Select 1, 4, 16, or 64 simulated hours per real second; does not resume automatically |
| WASD | Smooth camera movement in either pause state |
| Arrow keys | Camera movement while running |
| Mouse wheel over map | Zoom around cursor |
| Left click map | Inspect citizen, corpse, or food; repeat clicks cycle overlapping entities |
| F / Follow button | Toggle follow for a selected citizen; manual panning cancels it |
| TAB | Cycle all citizen identities, including deceased citizens |
| G / Home | Toggle grid / fit settlement in view |
| Wheel over sidebar | Scroll relationships, memories, and other inspection details |
| Wheel over event log | Scroll historical events; newest entries are at the bottom |
| L / Events button | Cycle notable, all, mortality, economy, needs, and magic filters |
| Click event row | Show complete structured event fields in the sidebar |
| + / - | Increase / decrease interface text scale |
| E / Economy button | Economic rates and daily-history charts; time controls remain active |
| F1 | Shortcut overlay; time stops while the overlay is open |
| Escape | Close help, or clear selection and follow |
| Window close | Exit; save a record if `--log PATH` was supplied |

Notable events omit repetitive movement, growth, sleep-hour and idle-rest records, which remain accessible in other filters and JSON. All rows come from actual engine events; there are no generated stories. Existing events include trades, eating, sleep, starvation, and corpse transitions. Future profession/magic events will appear when the engine emits them. The observer displays the emitted exhumation, animation, mana and undead lifecycle events without adding flavor events.

Rendering uses a private software frame buffer and presents only completed frames. SDL owns window resizing; the observer adopts the actual display size rather than recreating or forcing the window, including on tiling desktops. Rendering is capped at 60 FPS, with cached glyphs/fonts and only visible map cells drawn. Simulation speed is independent of redraws; updates are capped at eight steps and approximately eight milliseconds per frame (one engine step is indivisible). Backlog is bounded, so overloaded systems run slower rather than freezing to catch up. Pausing clears pending time. The engine itself retains all events in memory, so extremely long runs still grow memory usage. Target ThinkPad X270 performance has not been measured on that hardware.

`--gui --log /tmp/run.json` saves on normal window closure. `--gui --replay /tmp/run.json` verifies a record first and opens its final state paused; continuing it produces a longer reproducible run. `--days` applies to batch mode, not GUI duration. Original CLI commands below retain their behavior.

For screenshots, pause, select a citizen, and use the desktop screenshot tool. Capture the map, sidebar and event log together; include the seed and simulation time in the frame. No sprite assets or screenshot system dependency is needed.

GUI tests run without a desktop using SDL's dummy video driver:

```sh
SDL_VIDEODRIVER=dummy python3 -m unittest discover -s tests -v
```

Without pygame-ce installed, graphical smoke tests skip; simulation, camera, and observer-adapter tests still run.

## CLI and headless commands

From this directory:

```sh
python3 -m necropolis --observe --seed 47
python3 -m necropolis --seed 47 --days 30 --log /tmp/necropolis-47.json
python3 -m necropolis --replay /tmp/necropolis-47.json
python3 -m necropolis --seed 47 --days 30 --patches 15
python3 -m necropolis --seed 47 --days 30 --initial-trust 80
python3 -m unittest discover -s tests -v
```

In observation mode, press Enter to advance one hour, `d` to advance one day, `i` to inspect all citizens, `e` to view recent economic history, and `q` to quit. Add `--log PATH` to save the run when quitting. Batch mode advances `--days` days and prints the final map. `--patches` changes initial food abundance; the default is 65.

## Version 0.5.1 rules

Citizens receive unique, generated given names and family names with a Dunmer/Telvanni-inspired sound. These are original combinations rather than a roster of existing characters. Names appear in inspection and readable event logs; structured events retain stable citizen IDs, with names stored in the citizen state. A separate seeded random stream generates names so naming does not alter economic behavior or movement.

The seeded map contains renewable food patches and 20 citizens, each initially carrying two food units and 12 coins. Occupations repeat in ID order: farmer, forager, forager, merchant (five farmers, ten foragers, five merchants before necromancy assignment). By default the last forager becomes the one necromancer (five farmers, nine foragers, five merchants, one necromancer before miner assignment). With mines enabled, the first remaining forager becomes a miner (normally five farmers, eight foragers, five merchants, one necromancer, one miner). Use `--no-necromancy` to retain the original occupations. Each hour adds one hunger point. A citizen with at least six hunger points eats one stored unit, reducing hunger by six. Otherwise, they trade, produce, gather, move, or rest. Food and trade opportunities are visible within Manhattan distance three. Movement, gathering, farming, buying, and eating each take one hour for the acting citizen.

Farmers carry up to eight food units and produce one unit per work hour while standing on an original food patch, including a depleted patch. They stay there when their inventory is full. Foragers carry four units and gather naturally available food. Merchants carry twelve units, buy cheap local surplus until holding eight units, and also gather when possible. Farmers and foragers also buy when holding fewer than two units.

Sellers must be alive, have more than two food units, and have less than 12 hunger points. Asking prices are one coin for farmers, two for foragers, and three for merchants. Merchants pay at most two; others pay at most one unless their hunger reaches 12, when they pay up to three. Buyers select the cheapest affordable visible offer, then personal trust, distance, and seller ID; the relationship rules below describe refusals and discounts. Within one tile they transfer one food unit and the price in coins; otherwise they approach the seller. Trading has priority over production and gathering. Sales are passive for the seller and can occur several times per hour while surplus remains. Prices and occupations are simple fixed rules, not a market-clearing economy.

At 48 hunger points a citizen dies. Stored food is returned to their location; their coins stay with them and leave circulation until inheritance is implemented. Every 24 hours, original food patches below six units replenish by one. Dropped food does not create new renewable patches. Citizens can share tiles. Competition resolves in stable citizen ID order, which gives earlier IDs an advantage.

The display reports living population, stored and wild food, hungry citizens (at least 12 hunger points), total trades, and coins held by living citizens. The map shows `F` farmers, `M` merchants, `@` foragers, `&` crowds, `"` food, `+` persistent corpses, and `.` ground. Recent eating, gathering, production, trading, and starvation events appear beneath it. Inspection includes occupations and money. All events, including movement, growth, and resting, remain in the full log.

## Memory and relationships

Before each citizen acts, they observe tiles and inhabitants within three tiles. Personal food knowledge records location, last observed quantity, whether it is a renewable patch, and observation time. Out-of-view knowledge stays unchanged even if someone else consumes that food. Citizens pursue remembered food beyond their current view; returning to an empty location corrects their belief. Food memories expire after 72 hours without observation.

Citizens remember other inhabitants' last observed position, life status, surplus, and encounter time. If food knowledge offers no destination, a citizen with fewer than two food units and some money may approach a trusted seller's remembered location. Seller locations are pursued for at most 24 hours; actual trades always require a current local offer. Relationships persist even when location information becomes old, so a citizen does not remotely learn that someone has moved or died.

Trust is directional, bounded from 0 to 100, and starts at `--initial-trust` (default 50) on meeting someone. Each completed trade raises both participants' personal trust by five and increments their trade counts. Sellers refuse buyers they trust below 20. Buyers avoid sellers below 20 unless hunger reaches 24; desperation does not override the seller's refusal. Sellers grant a one-coin discount (minimum price one) to buyers they trust at least 75. Equally priced offers are ranked by highest buyer trust, then distance and seller ID. Trust currently grows through successful trades; grievances and trust losses await theft and conflict in a later social milestone.

Each citizen retains the last 12 remembered events: first encounters, their own trades, and trades or deaths witnessed within three tiles. Inspection (`i`) shows food knowledge and its age, relationships with trust and trade counts, remembered positions, and recent personal events. These are private experiences, not access to the complete world log.

The display also shows mean personal trust over all remembered directed relationships belonging to living citizens (including relationships with deceased citizens), and the minimum and maximum coin holdings of living citizens. This makes changes in who holds the fixed money supply visible.

## Fatigue and sleep

Each citizen has fatigue from 0 to 100, an individual awake fatigue rate of 3–5 points per hour, and a sleeping recovery rate of 10–14 points per hour. Initial fatigue varies from 0 to 40. These traits use a separate seeded random stream; they do not change map generation or names. Inspection shows each citizen's current fatigue, rates, and awake/asleep status. The map marks sleepers with `z` (crowds still use `&`), and the summary counts sleepers and tired citizens with fatigue at least 80.

Each hour hunger rises, including during sleep. An awake citizen gains fatigue, then eats if hungry and carrying food. Otherwise, at fatigue 80 or more they begin sleeping in place and recover for that hour. The decision uses projected fatigue for the hour, but an hour spent sleeping only reduces fatigue; it does not also add awake fatigue. At fatigue 10 or less they wake; their next action occurs the following hour. Ordinary idle `rest` remains awake time and does not recover fatigue.

Hunger of 12 wakes a sleeping citizen who has food, allowing them to eat that hour. With no stored food, hunger of six wakes them as soon as fatigue is 80 or below so they can seek food early. Hunger of 24 wakes them regardless of fatigue. When holding fewer than two food units and hunger reaches six, they postpone starting sleep until projected fatigue reaches 100; maximum exhaustion still requires a recovery break. A hunger-interrupted citizen gets an awake action before they can fall asleep again. Stored food is consumed before starting sleep, even at maximum fatigue. Starvation still occurs at hunger 48, whether awake or asleep.

Sleepers cannot move, gather, farm, trade, observe locations, or witness events. Their existing memories remain unchanged until waking and observing again. There are no beds, shelter requirements, day/night preferences, or fatigue penalties beyond time spent sleeping yet. Sleep begins from personal need rather than a universal bedtime.

Full logs record `sleep_start`, every `sleep` hour, and `wake` with its reason. The readable recent-event display shows sleep starts and wakes while omitting repetitive sleeping hours.

## Persistent corpses

Each death creates one physical corpse with a globally unique entity ID, former citizen ID and name, location, hour and cause of death, decay age, lifetime, preservation flag, and reanimation flag. The deceased citizen remains a historical record with a link to that body ID. Death still drops stored food and leaves coins with the deceased.

The default lifetime is 168 hours (seven days), configurable with `--corpse-decay-hours N`, where N must be positive. Bodies begin at age zero and age one hour at the start of each subsequent tick, before living citizens act. They are fresh for the first third of their lifetime, decaying for the second, and skeletal for the last. At their lifetime they disappear from the physical corpse collection. Very short lifetimes may skip a stage. Decay continues after living extinction.

`+` marks physical corpses and takes priority over food; living occupants and crowds take priority over corpses. Multiple bodies on one tile remain separate in inspection. The summary reports corpse count and available bodies. Inspection (`i`) includes each body's identity, death time/cause, location, decay stage/age, and preservation/reanimation flags. After decay, the corpse marker disappears and underlying food remains; citizen records, body ID links, and events retain the history.

Logs record `corpse_created`, `corpse_decay` on stage transitions, and `corpse_removed` on expiration. State records include current bodies and the next entity ID. Corpse availability excludes reanimated or fully decayed bodies. Buried grave bodies pause decay. Exhumation removes burial preservation; reanimation consumes the physical corpse while preserving its identity in the undead record and event history. Other preservation actions are not implemented.

The zero-patch commands below deliberately remove every renewable food source and demonstrate starvation and corpse decay. For normal observation, keep the default 65 patches: `python3 -m necropolis --observe --seed 47`. To inspect the corpse lifecycle in a controlled extinction run:

```sh
python3 -m necropolis --observe --seed 47 --patches 0 --graves 0 --no-necromancy --corpse-decay-hours 24
python3 -m necropolis --seed 47 --patches 0 --graves 0 --no-necromancy --days 3 --log /tmp/necropolis-corpses.json
python3 -m necropolis --replay /tmp/necropolis-corpses.json
```

## Finite graveyard and necromancy

The default world contains four old graves in a compact, seeded area of at most 3×3 tiles near the initial citizen who becomes the necromancer. The same placement is used with necromancy disabled. `--graves N` sets a finite initial supply (0–9, subject to map size). Graves never automatically refill or spawn more bodies. Villager deaths create separate exposed corpses as before; burial of newly deceased citizens is not implemented.

Old graves contain individually named bodies with unique entity IDs. Their former citizen ID, exact death time, and cause are unknown rather than invented settlement history. Buried bodies are preserved and unavailable for direct animation. `T` marks an occupied grave and `_` an emptied grave. Grave inspection shows the linked body and occupancy.

One existing forager becomes a necromancer (or the last citizen if a tiny world has no foragers). They carry six food units, use the ordinary hunger/sleep/trust/trade rules, and start with 30 mana. They discover bodies locally within three tiles, retain body locations for up to 72 hours, and correct memories on returning. They pursue magical work only when holding at least two food units. Exhumation takes an hour on the grave's tile, empties the grave permanently, and starts exposed decay. Animation is a separate hour on the exposed body's tile and costs 30 mana. It consumes the corpse exactly once and creates one undead identity linked to its source body and keeper.

When mana is below 30 and the necromancer knows bodies or has workers, an eligible magical work hour replenishes six mana (capacity 60). This costs awake time instead of producing food; there is no passive mana regeneration or free magical labor. Mana expenditure and replenishment are logged.

`U` marks active undead and `u` inactive undead. They consume no food, have no hunger or sleep, and move between assigned deposits and their keeper when mining is enabled. Maintenance checks occur after living citizens act, in undead ID order. A living keeper within six tiles sustains a binding, including while asleep. Each worker costs one mana every six hours, starting six hours after animation. Failed range, keeper death, or unpaid upkeep makes them inactive. A keeper who returns with at least one mana can reactivate a worker and pay its next interval. Each inactive hour permanently removes one of 72 integrity points; at zero the worker disappears with a logged event. Maintained workers do not lose integrity. Supply, upkeep, the keeper's needs, and deterioration limit the population; there is no arbitrary worker cap.

Undead can now mine known deposits and deliver ore to their keeper. `--mines 0` retains the previous idle lifecycle for isolated comparisons. Inspect graves, corpses, necromancers and undead in either observer; the graphical magic filter exposes their events.

```sh
python3 -m necropolis --gui --seed 47
python3 -m necropolis --seed 47 --days 10 --log /tmp/necropolis-magic.json
python3 -m necropolis --replay /tmp/necropolis-magic.json
python3 -m necropolis --seed 47 --days 10 --no-necromancy
```

## Ore, mining, and external trade

Three seeded, finite mines start with 120 ore each. The first is near the graveyard/keeper starting area, the second near the initial miner, and further sites are seeded elsewhere. Deposits never regenerate. `--mines 0` disables the ore economy and miner assignment. `--ore-per-mine N` sets positive initial deposits. `^` marks a mine, `v` an exhausted deposit, `P` a miner, and `*` dropped ore. Mine, inventory, worker and settlement inspection show ore and extraction/export/import totals.

One existing forager becomes a living miner when one is available. Miners retain hunger, sleep, six-unit food capacity and ordinary trade rules. They discover mines within three tiles and remember quantity/location for 72 hours. With at least two food units and ore inventory below eight, they move toward a remembered nonempty site or extract one unit in an hour on its tile. Deposits belong to no individual yet; extracted ore belongs to the worker. Stale memories are corrected on observation.

Necromancers assign undead to deposits they personally know. With mining enabled, they require a known nonempty mine and a nonzero configured export allowance before pursuing new animation, and can spend an hour assigning an idle worker. Initial assignment can accompany animation. This is a simple demand signal from an available export market, not dynamic market pricing or perfect information about buyers. Mana replenishment for existing bindings remains possible regardless of mine knowledge.

Active undead take one action per hour, starting the hour after animation: walk, extract one unit, or deliver. They carry ore themselves; nothing is teleported to the keeper. At four carried units they approach their keeper and transfer as much as fits within one tile, up to the keeper's eight-unit ore capacity. Mine output therefore compensates the keeper for magical labor through actual owned goods. A full keeper inventory blocks delivery. Inactive workers cannot mine, move or deliver. Exhausted deposits leave workers idle until reassignment. Existing upkeep/range/deterioration still applies; carrying ore does not prevent maintenance failure.

Awake merchants discover nearby living ore holders within three tiles, approach to within one tile, and buy one ore per action for one coin, subject to mutual trust of at least 20. Buyer ore capacity is eight and funds cannot go negative. Sales are passive for the holder, so miners and necromancers receive payment without an extra simultaneous action. Successful ore trades update relationships like food trades. Ore holders can approach remembered merchants when carrying at least four ore or running low on food; the location can be stale.

A merchant with ore and room for two food units can spend an hour exporting one ore for two food. This abstract external market requires no travel to a new map building. The settlement-wide quota is eight ore per simulated calendar day, configurable with `--daily-ore-exports N` (zero closes the market). It resets at midnight before citizen actions. Merchants consume food and obey sleep; export actions are unavailable while asleep. Export transfers no coins: the log records ore leaving and two food units entering, while local purchases redistribute the original coin supply. Merchants can then eat or sell imported food through the existing local economy. Importing food does not guarantee its equitable distribution.

Ore carried by a dying citizen or deteriorating undead is dropped at its location rather than deleted. Miners, merchants and necromancers can collect one local dropped unit per hour when holding at least two food units and having capacity. UI statistics distinguish ore mined, held, dropped, and exported, and food imported. The ore balance is: initial deposits = remaining deposits + all inventories + dropped ore + exports. Food accounting includes imported units; internal trades and deliveries create neither food nor ore.

```sh
python3 -m necropolis --gui --seed 47
python3 -m necropolis --seed 47 --days 10 --log /tmp/necropolis-ore.json
python3 -m necropolis --replay /tmp/necropolis-ore.json
python3 -m necropolis --seed 47 --days 10 --no-necromancy
python3 -m necropolis --seed 47 --daily-ore-exports 0
```

Crafting, equipment, mine ownership, dynamic prices, wages/contracts beyond ore sales, and inheritance remain planned. The market does not mint money, and limited deposits, daily export flow, inventories, merchant cash, food and magical upkeep constrain economic activity.

## Economic observation

Press `E` or the Economy button in the GUI to view food production/consumption/import rates, living versus undead ore extraction, export flow, and mana replenishment/animation/upkeep costs. Daily-history charts show living population, total food stock, held/dropped ore, and living coin inequality. Press `E` or Escape to return to the map. Pause, step, and speed controls still work; the dashboard does not stop time or change decisions. In the CLI observer, `e` prints the latest ten daily history rows; batch results also show the current food balance and inequality.

Flows count actual events over the latest 24 simulated hours. Before a full day exists, counts are divided by elapsed hours and multiplied by 24; the interface explicitly reports the window length. These are normalized observed rates, not forecasts. Food production includes farm output and natural patch growth; gathering, trades and deliveries are transfers and do not count as production. Net food rate is production plus imports minus consumption. Ore output is split by living/undead extraction. Mana costs distinguish animation from upkeep.

History records an initial point and a sample after every 24 hours, including after living extinction. Each point contains population, active/total undead, food and ore stocks, remaining deposits, mana, occupational counts, individual living coin holdings, Gini inequality, and measured flows/rates/totals. Charts show the latest 120 daily samples; the complete history is retained in the record's `economy_history` field. `state.economy` contains live measurements. Replay verifies economic history as well as events and final state.

Gini describes coin holdings among living citizens only: zero means equal holdings; higher values mean more concentration. It is defined as zero when no living citizens or no circulating coins remain. This is not a total-wealth measure: it excludes food, ore, assets and deceased citizens' coins.

Undead inspection reports observed conditions such as travelling to a mine, mining, delivering, keeper storage full, depleted deposits, and missing upkeep/range/keeper. Citizen inspection flags low food, empty coin holdings, full ore storage, and mana below animation cost. These are descriptions of current state, not fabricated thoughts or guarantees about the next action.

Measurements live in a pygame-independent passive module. They do not consume RNG, create resources, or feed back into agent decisions. Crafting, warriors and battlemage preparation remain planned; this milestone adds evidence for assessing the economy before those systems arrive.

## Reproduction and persistence

JSON records contain the simulation version, seed, configuration, every structured event, and final state. Replay re-runs the recorded number of hours from the initial configuration and checks both the complete event sequence and final state. This requires the same simulation version and a compatible Python random implementation. Records persist history and verify reproduction; loading a saved run for continued simulation is not yet implemented.

Logs from earlier versions are incompatible with version 0.5.1 and are rejected explicitly. There is no disease or direct citizen control in this milestone. Later mechanics follow the roadmap in [AGENTS.md](AGENTS.md). Outcomes arise from resource availability, personal needs, knowledge, relationships, and local decisions.
