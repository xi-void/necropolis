# NECROPOLIS

## Project vision

NECROPOLIS is an autonomous dark-fantasy settlement simulator with an emphasis on magic, necromancy, emergent economies, and evolving societies. It combines the emergent complexity of Dwarf Fortress, the settlement simulation of SimCity 2000, and a miniature artificial society. Develop toward a persistent, procedurally generated world inhabited by autonomous individuals.

The player observes what inhabitants do to each other. They do not directly control individual citizens. Aim for a world with history and no predetermined story.

**Simulate systems and their interactions, not predetermined stories or outcomes.** Necromancy should initially be a practical magical occupation, without an automatic moral judgment or social prohibition.

The presentation should have a distinctly grim, late-1990s simulation aesthetic: ASCII maps, dense but readable information, restrained colors, and chronological event logs. Make the simulation legible without flattening its complexity.

## Development principles

- Start with Python and the standard library. Introduce dependencies only when they solve a demonstrated need. Keep the core simulation runnable without a graphical interface, external services, or LLMs.
- Build the smallest working simulation first. Every version must be runnable and observable, with meaningful behavior rather than scaffolding for a future game.
- Derive outcomes from agent behavior, resources, relationships, and environmental conditions. Do not script famines, rebellions, cooperation, or collapse to force a narrative.
- Keep the simulation independent of its display so the same rules can support interactive observation and unattended experiments.
- Prefer clear, inspectable rules over elaborate abstractions. Add complexity when it produces a meaningful new behavior.
- Preserve deterministic seeds and replayable event logs from the beginning.
- Balance through measurable resource costs, scarcity, competing incentives, and feedback loops. Investigate unexpected outcomes before changing rules; a collapsed civilization may reveal a useful interaction rather than a defect.

## Existing functionality verified in the codebase

The current local implementation is version **0.5.1**, as declared in `necropolis/__init__.py`. This section describes implemented behavior; the roadmap below describes proposed additions.

- **World and agents:** a seeded 32-by-14 ASCII map with 65 original renewable food patches and 20 citizens by default. Citizen IDs are stable, and unique Dunmer/Telvanni-inspired names use a separate seeded random stream. Citizens share tiles and choose their own actions.
- **Occupations and food:** five farmers, ten foragers, and five merchants, assigned in repeating ID order before replacing the last forager with a necromancer by default. `--no-necromancy` retains original roles. Farmers produce one food unit per work hour on original patches; foragers gather; merchants buy local surplus and can also gather. Food capacities are eight, four, and twelve respectively. Original patches below six units grow one unit daily; dropped food creates no new renewable patches.
- **Survival and death:** citizens begin with two food units. Hunger rises by one each hour, including while asleep; eating one unit reduces hunger by six. Hunger 48 causes starvation. Death stops activity, drops stored food locally, and leaves money with the deceased. Dead citizens remain as historical records linked to separate corpse entities with unique IDs, former identity, location, death time/cause, decay, preservation and reanimation flags. Corpses age hourly from the tick after death and disappear after a configurable lifetime (default 168 hours); stage transitions and removal are logged. `+` marks current physical corpses. Four finite old graves supply preserved bodies by default; necromancers exhume and reanimate eligible exposed bodies. Occupied graves do not refill. Ancient identity/death metadata is explicitly unknown where unsupported.
- **Economy:** citizens begin with 12 coins each, totaling 240. Trades transfer one food unit for money within one tile; sellers are discovered within three tiles and must be awake, alive, below 12 hunger, and holding more than two food units. Base prices are one coin from farmers, two from foragers, and three from merchants, with trust discounts and occupation/hunger-based purchase limits. Coins are conserved across all citizens; money held by deceased citizens leaves living circulation. Mana supports animation/upkeep and costs replenishment time. Finite mine deposits, living/undead extraction, owned ore inventories and merchant ore-for-food exports are implemented. Equipment and inheritance remain planned.
- **Knowledge and relationships:** local perception uses Manhattan distance three. Food memories expire after 72 hours, and remembered seller locations are pursued for up to 24 hours. Out-of-view information is not remotely refreshed. Directional trust starts at configurable initial trust (default 50), rises by five per completed trade, affects partner selection/refusal, and grants discounts at 75. Each citizen retains 12 encounter or witnessed trade/death memories. Trust losses, grievances, factions, and attitudes toward magic are not implemented.
- **Sleep:** seeded individual fatigue rates of 3–5 per awake hour, recovery rates of 10–14 per sleeping hour, and initial fatigue of 0–40. Fatigue is bounded to 0–100; citizens generally start sleeping at 80 and finish at 10 or below. Hunger can interrupt or postpone sleep; empty inventories trigger food-seeking from hunger six, and low reserves postpone sleep until maximum exhaustion. Sleeping hours recover fatigue without an awake fatigue charge. Sleeping blocks work, movement, trade, and new observations. Shelter, beds, and universal bedtimes are absent.
- **Observation and reproduction:** CLI observation, optional pygame-ce graphical observation with camera/selection/history controls, hourly/daily stepping and inspection, batch runs, configurable seeds/food abundance/initial trust, structured events, and JSON records with configuration, version, events, and final state. Replay re-runs from the initial configuration and verifies events and state. Earlier simulation versions are rejected. Loading a saved state directly for continuation, live interventions, and a multi-seed experiment command are not implemented; the GUI can advance a verified world after deterministic re-execution of a record.

`README.md` documents current commands and detailed thresholds. Existing standard-library tests cover deterministic replay, resource accounting, local knowledge, names, trust, sleep, and corpse identity/decay.

## Architecture to preserve and extend

### Graphical observer conventions

The optional pygame-ce interface is implemented in `necropolis/gui.py`, launched with `python3 -m necropolis --gui`. `requirements-gui.txt` is the only graphical dependency. Preserve CLI observation and headless defaults; import pygame lazily only for GUI requests. The observer itself does not change rules or schemas; the current 0.5.1 version adds passive economic measurements and persisted history to the existing ore/necromancy rules.

`necropolis/observer.py` is a pygame-independent adapter for snapshots, detached inspection, event indexing, pause/speed scheduling, and camera coordinate conversion. It advances only through `World.step()` and refreshes snapshots after updates. Renderers consume snapshots or read existing public configuration/events; they must never mutate agents, resources, events, or RNG state. Do not use redraws as simulation ticks.

Draw into a private software frame buffer and present completed frames in one blit. Adopt SDL display-surface size changes; never call `set_mode` from resize notifications or force a minimum size against the window manager. Keep software rendering capped at 60 FPS, draw only visible grid cells, and cache fonts/glyphs. Update event indexes incrementally rather than rescanning history per frame. Bound catch-up to eight engine steps and an approximate eight-millisecond budget per frame; one engine step remains indivisible. User input, simulation advancement, and drawing have separate methods. Changes to panels/camera/selection must not consume simulation randomness.

Use existing state only: the GUI currently distinguishes living occupations, sleepers, food, corpses, and ground; render the implemented graves, necromancer and active/inactive undead alongside other entities; also render miners, finite mine sites, exhausted deposits and dropped ore; do not display invented age, buildings, crafting, or profession changes. Preserve citizen selection and death links after corpse removal. Event filters display actual emitted records; full fields are inspectable by selecting a row. Use a restrained dark palette and ASCII glyphs, with no shaders or sprite systems.

Keep `tests/test_observer.py` runnable without pygame for adapter/camera tests; optional graphical tests use SDL's dummy driver and skip when pygame-ce is absent. Test state/RNG separation, seeded equivalence, pause/step behavior, coordinate selection, window controls, and resizable rendering. Document new bindings, scaling, dependency installation, and limitations in `README.md`.

### Simulation conventions

- Keep Python 3.10+ and the standard library unless a demonstrated need justifies a dependency. `necropolis/simulation.py` owns dataclass models, `Config`, `World`, action rules, state serialization, and replay. `necropolis/__main__.py` owns CLI controls, rendering, and inspection; `necropolis/names.py` owns name generation. Keep simulation logic independent of presentation.
- Each tick is one hour. The current implementation increments time first, ages existing corpses, processes living citizens in stable ID order with immediate state mutation, then applies daily patch growth. Later citizens can observe earlier actions in that hour. Preserve and document this ordering unless an explicit change is justified; the conceptual loop below does not imply a simultaneous action engine.
- Use controlled random streams and explicit simulation time. Names and sleep traits already use separate seeded streams. Comparative runs must preserve common initialization when a feature is toggled so incidental random draws do not obscure its effect.
- Add simple corpse, undead, resource, and site models as needed. Split modules when responsibilities warrant it; do not introduce a framework or general entity system merely in anticipation of future mechanics.
- New professions require extending capacity, price, action, initialization, and display rules, which currently assume farmer/forager/merchant. Undead require their own lifecycle rather than passing through living hunger, sleep, and starvation rules.
- Citizen lookup uses an explicit ID map; corpses use a monotonic entity ID allocator starting after initial citizen IDs, with the next ID included in state. Extend this scheme for future entities rather than resolving actors through list positions or reusing removed corpse IDs. Preserve former citizen identities and historical references even after a corpse decays.
- Extend `World.state()`, records, event schemas, inspection, and replay verification together. Bump the simulation version when rules or schemas change and document compatibility. Resumable persistence is a separate planned capability: it must capture random generator state, original patch membership, ID allocation, and other state needed for continuation, not just the current displayed snapshot.

## Inhabitants

Develop each inhabitant as an autonomous individual with:

- **Needs:** hunger, shelter, sleep, and security.
- **Resources:** money, food, and possessions.
- **Personality:** greed, sociability, and risk tolerance.
- **Memory:** witnessed events, relationships, and grievances.
- **Knowledge:** a limited understanding of the surrounding world.

Introduce these capabilities incrementally. Hunger, fatigue, food, money, limited knowledge, and basic memory/trust already exist; shelter, security, broader possessions, personality, and grievances remain planned. Living necromancers and warriors retain ordinary survival needs; undead have a distinct maintenance model.

Nobody has perfect information. Agent decisions must use local observations, personal knowledge, and memories rather than unrestricted access to world state. A merchant may believe famine is imminent while a farmer knows there is enough grain for months. Beliefs can be incomplete, outdated, or wrong.

## Simulation loop

Each tick follows a defined sequence:

1. Read the current world state: resources, buildings, and environment.
2. Let agents perceive their local surroundings and recall relevant memories.
3. Let agents choose actions according to needs, personality, knowledge, and available opportunities.
4. Resolve interactions such as trade, cooperation, theft, and conflict.
5. Apply consequences to the world and record significant events.
6. Advance simulation time; the resulting state becomes the next tick's reality.

Make action ordering and conflict resolution explicit and deterministic. Separate the world's actual state from what each agent believes about it.

## Roadmap: completed foundations and planned phases

| Foundation | Current status |
| --- | --- |
| 0.1 | Implemented: ASCII map, 20 autonomous citizens, food, hunger, starvation |
| 0.2 | Implemented: occupations, production, trading, seeded names |
| 0.3 / 0.3.1 | Implemented: local memory, trust, relationships, fatigue and sleep |
| 0.3.2 / Phase 1 | Implemented: persistent corpses, deterministic decay, inspection, lifecycle events and replay |

The original future goals remain: scarcity responses, theft, cooperation and conflict; migration, births and inheritance; and emergent institutions, factions and authority. Integrate them with the phases below rather than discarding them. Death already exists. Previous tentative 0.4–0.6 assignments are deferred; these phases express dependency order, not committed release numbers. Every stage must produce a runnable, observable result.

### Phase 1: persistent corpses — implemented in 0.3.2

Extend the existing starvation path to create exactly one persistent corpse per death. Store a unique entity ID, former citizen ID and name, location, simulation time and cause of death, decay state, and reanimation status. Preserve the dead citizen's historical identity independently of the physical corpse.

Advance decay deterministically in simulated hours until an unpreserved corpse disappears. Define the decay duration as a documented parameter; preservation and animation later alter this lifecycle. A corpse is an interactable resource, with explicit availability rules for future preservation and reanimation, rather than another map decoration. Reanimation must consume or mark the original corpse so it cannot create multiple workers.

For this milestone, add corpse inspection/map representation, creation and decay/removal events, current corpse count, and serialization/replay coverage. Preserve current food drops and deceased coin accounting. No necromancer, mining chain, or resurrection action is needed yet. Verify one corpse per death, stable identity links, deterministic decay, and retention of historical references after physical removal.

### Phase 2: necromancers and undead labor — lifecycle implemented, productive labor planned

Assign one of the existing living citizens the necromancer profession initially, rather than adding a free extra inhabitant. They still eat, tire, sleep, gather or trade for survival, and observe locally. They search for eligible corpses using observation and memory, spend mana to animate them, and maintain workers through magical upkeep. Prefer existing deaths as the corpse supply; do not add killing living citizens as a way to force necromancy into a run.

Bound active workers through explicit mana availability, regeneration or acquisition, animation cost, per-worker upkeep, and later skill. Avoid arbitrary settlement population caps or unexplained worker limits. Define what happens when upkeep fails: deterioration or inactivity, with logged state changes and no productive work from inactive workers. Specify maintenance range/timing, ownership, and what follows the keeper's death before relying on them economically.

Undead need no food and initially perform mining labor. Their lifecycle must distinguish a dead living citizen, an available corpse, and an active or inactive undead worker. Preserve identity links without counting the same body as both available corpse and worker. Necromancers assign work from locally known demand and opportunities, not global market knowledge.

**Dependency:** useful undead mining requires the minimal ore/mine and market systems in Phase 3. Introduce a mana pool with explicit replenishment, animation, and upkeep first; then add the minimal mining/export loop before releasing productive undead labor. Do not present ore with no buyer or use as a completed economic feature.

### Phase 3: economic diversification

Add resources incrementally: existing food supports living survival; ore comes from mining; mana funds animation and upkeep; equipment later consumes mined resources. Keep existing foragers useful and retain the food economy and sleep/trust rules.

| Profession | Economic function and costs |
| --- | --- |
| Farmer | Produces food and consumes living survival resources |
| Forager | Gathers available food; existing occupation retained |
| Miner | Extracts ore at known mine sites; needs food and sleep |
| Merchant | Exchanges goods locally and connects ore to an external food market |
| Warrior | Provides protection at a food and labor opportunity cost |
| Necromancer | Animates and maintains labor using mana, time, and ordinary living needs |
| Undead worker | Performs labor without food consumption, subject to magical upkeep and deterioration |

Start with mine sites, ore extraction, and one transparent merchant-mediated abstract external market exchanging ore for food. Specify exchange rates, action time, capacity, and stock or flow constraints. Log ore leaving and food entering the settlement as external resource flows, not unexplained creation or changes to the conserved coin supply. Do not implement all crafting chains at once; equipment production follows only when ore exchange and mining are useful.

Make inventories, ownership of mined output, compensation for living miners and necromancers, and the allocation of mana explicit. An affordable mechanism for funding magical labor is a dependency, not an assumed free service. Undead save food but require a living keeper, magical resources, and time; failure of those inputs must affect output. Calibrate costs through measured runs rather than forcing equal success rates.

### Phase 4: warriors and settlement defense

Introduce warriors and defensive preparations before invasions. Warriors consume food, sleep, and provide a measurable defensive capability while diverting labor from production. Define training or readiness and protection coverage; add equipment requirements after their production/exchange exists.

Hostile threats become possible only when settlements have meaningful defensive options. Threats and battles must obey observable rules with counterplay; avoid arbitrary population deletion or scripted defeat. Undead soldiers, defensive structures, and competing military strategies are later extensions, not prerequisites for the first warrior milestone.

### Phase 5: emergent social consequences

After the economic and magical loops are stable, extend existing memories, trust, and relationships into attitudes, grievances, cooperation, theft, conflict, and factions. Living workers may be displaced by undead labor; dependence on a keeper may make their death economically disruptive. Control of mines and mana may concentrate wealth. These are hypotheses to investigate, not events to trigger on a timer or population threshold.

Different attitudes toward undead should arise from personal experiences, incentives, and later personality or culture. Do not universally prohibit necromancy. Schools and transmission of magical knowledge require explicit learning and succession rules; economic/magical factions and authority require interactions and resources that sustain them. Integrate the retained goals of migration, births, inheritance, and institutions when their dependencies exist.

### Recommended implementation order

1. Completed: corpse entities, deterministic decay, inspection, events, and verified replay.
2. Implemented in 0.4.0: finite seeded graveyard, local discovery, exhumation, living necromancer needs, time-funded mana, animation, and inactive/maintained undead lifecycle. Graves hold preserved bodies once, with no automatic replacement. Undead can mine in 0.5.0; disabling mines retains the idle lifecycle.
3. Implemented in 0.5.0: finite ore sites, one living miner, undead mining/delivery, local ore ownership/payments, and daily-limited merchant ore-for-food exports. Assignments use known mines and configured export availability. Dynamic demand/prices and formal labor contracts remain planned; retain living mining as a comparison.
4. Economic observation is implemented in 0.5.1: rolling flow rates, daily stock/population/coin-distribution history, and explicit worker conditions. Next add smiths and weapons, warriors, and battlemage preparation as needed; destruction spell practice and readiness should precede hostile threats.
5. Economic/magical attitudes and consequences, followed by the retained demographic and institutional goals as supporting mechanics mature.

Steps 2 and 3 overlap intentionally: animation can be observed before a full economy exists, but productive undead labor needs ore demand. Keep each intermediate build inspectable and avoid unrelated manufacturing, warfare, or cultural systems.

## Determinism, history, and experiments

- Use an explicit simulation seed and a controlled random number generator. Avoid wall-clock time and incidental iteration order as sources of simulation behavior.
- Record the seed, initial configuration, and simulation version needed to reproduce a run.
- Give events simulation timestamps, stable participant identifiers, event types, and relevant consequences. Keep structured event data separate from its human-readable presentation.
- Define and document how logs support replay. A readable event summary alone must not be presented as sufficient to reconstruct world state.
- Record interventions with their timing and parameters so they can be reproduced.
- Support comparisons between otherwise identical runs with one changed parameter, such as initial trust, over a defined duration such as 500 days.
- As the relevant mechanics arrive, expose metrics for population, inequality, cooperation, and collapse. Define how each metric is calculated.
- Extend persisted state to cover corpses, undead, mana, sites, and resource ownership when added. Preserve world history after entities decay or change form; resumable saves remain a planned extension to current replay records.
- Support otherwise identical seeded comparisons with and without necromancy once implemented, recording the feature setting and keeping common initial conditions stable. Current CLI comparisons support seed, food abundance, initial trust, necromancy, graves, mine count/deposits and daily export allowance.

Planned metrics must distinguish stocks from rates and use explicit observation windows:

| Metric | Proposed measurement |
| --- | --- |
| Living and undead population | Separate living count and active/inactive undead counts |
| Food and starvation | Stored/wild food, production/consumption/import flows, hungry citizens, starvation deaths per interval |
| Ore production | Ore stock, extraction per interval, exported amount |
| Mana consumption | Available mana, replenishment, animation/upkeep consumption, missed upkeep |
| Occupational distribution | Living counts by profession; undead assignments separately |
| Economic stability | Trade volume, unmet affordable demand, net food flow, and wealth distribution; avoid an unexplained composite score |
| Mortality and corpse availability | Deaths by cause per interval, eligible corpses, decay stages, removals and animations |
| Survival and collapse | Time to extinction and duration of food/maintenance failure; distinguish living extinction from surviving undead activity |

Current summaries already show living count, food stocks, hungry count, trades, circulating coins, coin range, mean trust, sleepers, and tired citizens. Corpse count and available body count are also implemented. Mana stock, occupied graves and active/total undead counts are implemented. Ore extraction, inventories, dropped ore, exports and food imports are implemented; broader stability metrics remain planned. Do not claim a collapse merely from a threshold crossing without documenting the criterion.

An illustrative chain might be a poor harvest report, higher grain prices, stockpiling, theft, an arrest, declining trust, and starvation. This is an example of a possible outcome, never a scripted sequence or required result. Another seed may produce cooperation from the same environmental pressure.

## Player interaction

Develop toward three modes:

- **Observer:** watch the simulation, inspect inhabitants, and read its event history.
- **Intervention:** change environmental conditions, resource abundance, or disease conditions once those systems exist.
- **Experiment:** run many seeds and compare outcomes using consistent metrics.

Interventions change conditions. They must not issue direct commands to citizens or predetermine their reactions.

## Validation

When adding or changing simulation mechanics, verify the behavior with focused standard-library tests and reproducible runs:

- The same seed, configuration, and recorded interventions produce the same results.
- Resource accounting is consistent; production, consumption, transfer, and loss have explicit causes.
- Agents act on information they could possess.
- The current milestone runs and exposes enough information to understand its behavior.
- Replay reproduces the state or outcomes promised by the documented replay mechanism.
- For corpses and undead, each transition preserves identity, avoids duplicate bodies/workers, and records explicit causes. Inactive workers cannot produce, and upkeep must debit the recorded mana source.
- For external trade, ore exports and food imports explain changes to settlement resources. Retain existing conservation checks for internal food transfers and coins, adapting them only for explicitly introduced sources and sinks.
- Compare multiple seeds and feature configurations; separate implementation defects from legitimate scarcity, mortality, or collapse.

Do not require a particular dramatic story as a test outcome. Test underlying rules and invariants; use multiple seeds to investigate emergent patterns.

Document the run command, available controls, seed selection, and verification commands as they become available. Do not describe planned capabilities as implemented.

## Long-term direction

The following are speculative possibilities, not immediate requirements: necromantic schools and magical research; autonomous undead and liches; magical ecology and geographic mana fields; undead armies and warfare; religion, ideology, and cultural evolution; inheritance and persistent family histories; ruins and ancient civilizations; multiple settlements with independent economies; and generational changes in institutions and magical traditions. Schools and inheritance also appear as later roadmap goals, but their broader forms remain exploratory.

The settlement should accumulate an actual historical record: wars, dynasties, extinctions, and social transformations arising from its rules.

A later, optional LLM layer may interpret significant events or generate chronicles and documents grounded in that record. It must not control individual agents, invent historical facts, or become a dependency of the core simulation. Pursue this only after the underlying simulation and archives justify it.

## Current necromancy rules (0.4.0)

Use `README.md` for exact lifecycle parameters. One existing forager becomes a necromancer; four old graves form a finite, compact seeded area nearby. Ancient bodies have no fabricated citizen ID or death date. Body memory uses local perception and expires after 72 hours. Exhumation and animation each take a separate hour on the body tile; animation costs 30 mana and consumes one physical body. Necromancers prioritize survival and sleep and perform magic only with at least two food units. Replenishment adds six mana per work hour when below 30, with capacity 60. Each undead requires one mana per six hours from a living keeper within six tiles; checks occur after citizen actions. Failed maintenance deactivates the worker and loses one of 72 integrity points per inactive hour. Undead never consume food; mining is implemented in 0.5.0. Grave, body, keeper and undead IDs, mana flows, lifecycle events and snapshots participate in replay. New villager burial, richer demand-based assignments and formal labor contracts remain planned. Ore sales now fund miners and keepers as described below. Original rule tests disable the new optional systems to isolate their invariants; new lifecycle/replay tests cover the default world.

## Current ore economy rules (0.5.0)

Three finite seeded deposits hold 120 ore each by default, with sites near initial keeper/miner areas plus seeded remote sites. One remaining forager becomes a miner. Living miners retain food/sleep needs; undead work only when maintained. Each extraction takes one hour on the site and yields one owned unit. Inventory limit is eight ore. Workers carry batches to their keeper and deliver within one tile; dropped stocks survive citizen death or undead deterioration. Merchants buy local ore for one conserved coin per unit under mutual trust, then export one ore for two food units in a separate action. A settlement-wide quota of eight ore per day resets at midnight. Market imports/exports are explicit recorded flows. Mine discovery and quantities use local perception and 72-hour memory. Necromancers select known deposits and configured export availability as the first demand signal; dynamic market knowledge is not assumed. Step order is time/quota reset, corpse decay, living actions, undead maintenance, undead movement/extraction/delivery, daily food growth. Inspect sites, stocks and flows in both observers. Keep ore/food/coin balance and serialized replay tests; the simulation and GUI stay independent. Disable mines in tests of pre-existing isolated rules. Equipment, mine ownership and formal contracts remain later stages.

## Economic observation conventions (0.5.1)

`necropolis/economy.py` passively consumes actual emitted events and maintains 24-hour flow buckets, cumulative totals, and daily history. It takes no random draws and must not influence agent decisions or mutate resources. Food production counts farming and growth, not gathering/trading; balance includes imports and consumption. Ore extraction distinguishes living and undead labor. Mana costs distinguish animation and upkeep. Normalize partial windows to per-day rates and disclose elapsed hours; these rates are observations, not forecasts. Gini covers living coin holdings only and is zero for empty population or coin supply. Sample at hour zero and after each 24-hour tick, even following extinction. Serialize all samples in `economy_history` and verify them during replay; retain current live measurements in `state.economy`.

The GUI E dashboard plots the latest 120 daily points, with time controls active. The CLI e command shows recent daily rows. Inspection describes worker/stock conditions from public snapshots; do not invent thoughts or inferred choices. Incrementally copy history to the observer without duplicate rows, retain the complete archive in records, and keep redraws/state inspection read-only. Test history accounting, rate windows, replay/tamper detection, and seeded rule/RNG equivalence with measurement disabled. Smiths, equipment, warriors, and battlemages remain planned following the user preference for economic observation first.
