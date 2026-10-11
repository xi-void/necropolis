# NECROPOLIS

## Project vision

NECROPOLIS is a persistent, procedurally generated settlement inhabited by autonomous individuals. It combines the emergent complexity of Dwarf Fortress, the settlement simulation of SimCity 2000, and a miniature artificial society.

The player observes what inhabitants do to each other. They do not directly control individual citizens. Aim for a world with history and no predetermined story.

The presentation should have a distinctly grim, late-1990s simulation aesthetic: ASCII maps, dense but readable information, restrained colors, and chronological event logs. Make the simulation legible without flattening its complexity.

## Development principles

- Start with Python and the standard library. Introduce dependencies only when they solve a demonstrated need. Keep the core simulation runnable without a graphical interface, external services, or LLMs.
- Build the smallest working simulation first. Every version must be runnable and observable, with meaningful behavior rather than scaffolding for a future game.
- Derive outcomes from agent behavior, resources, relationships, and environmental conditions. Do not script famines, rebellions, cooperation, or collapse to force a narrative.
- Keep the simulation independent of its display so the same rules can support interactive observation and unattended experiments.
- Prefer clear, inspectable rules over elaborate abstractions. Add complexity when it produces a meaningful new behavior.
- Preserve deterministic seeds and replayable event logs from the beginning.

## Inhabitants

Develop each inhabitant as an autonomous individual with:

- **Needs:** hunger, shelter, sleep, and security.
- **Resources:** money, food, and possessions.
- **Personality:** greed, sociability, and risk tolerance.
- **Memory:** witnessed events, relationships, and grievances.
- **Knowledge:** a limited understanding of the surrounding world.

Introduce these capabilities according to the roadmap; the first version does not need every trait or system.

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

## Roadmap

| Version | Playable scope |
| --- | --- |
| 0.1 | ASCII map, 20 autonomous citizens, food, and hunger |
| 0.2 | Occupations, resource production, and trading |
| 0.3 | Individual memory, trust, and social relationships |
| 0.4 | Scarcity, theft, cooperation, and conflict |
| 0.5 | Migration, births, deaths, and inheritance |
| 0.6 | Emergent institutions, factions, and authority |

Prioritize version 0.1 before building later systems. The first broader milestone is 20 ASCII inhabitants who can feed themselves, trade, and occasionally make catastrophically poor decisions. Trading belongs to version 0.2.

## Determinism, history, and experiments

- Use an explicit simulation seed and a controlled random number generator. Avoid wall-clock time and incidental iteration order as sources of simulation behavior.
- Record the seed, initial configuration, and simulation version needed to reproduce a run.
- Give events simulation timestamps, stable participant identifiers, event types, and relevant consequences. Keep structured event data separate from its human-readable presentation.
- Define and document how logs support replay. A readable event summary alone must not be presented as sufficient to reconstruct world state.
- Record interventions with their timing and parameters so they can be reproduced.
- Support comparisons between otherwise identical runs with one changed parameter, such as initial trust, over a defined duration such as 500 days.
- As the relevant mechanics arrive, expose metrics for population, inequality, cooperation, and collapse. Define how each metric is calculated.

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

Do not require a particular dramatic story as a test outcome. Test underlying rules and invariants; use multiple seeds to investigate emergent patterns.

Document the run command, available controls, seed selection, and verification commands as they become available. Do not describe planned capabilities as implemented.

## Long-term direction

The settlement should accumulate an actual historical record: wars, dynasties, extinctions, and social transformations arising from its rules.

A later, optional LLM layer may interpret significant events or generate chronicles and documents grounded in that record. It must not control individual agents, invent historical facts, or become a dependency of the core simulation. Pursue this only after the underlying simulation and archives justify it.
