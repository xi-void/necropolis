"""Original names with an angular, Dunmer/Telvanni-inspired sound."""

import random


GIVEN_ROOTS = ("Nel", "Vel", "Dral", "Sery", "Arv", "Fery", "Bal", "Ther",
               "Vory", "Dren", "Nir", "Rav", "Ulv", "Sadr", "Trel", "Mav")
GIVEN_ENDINGS = ("as", "yn", "is", "on", "ara", "ira", "eth", "ane",
                 "oren", "ena", "ath", "eni")
FAMILY_ROOTS = ("Tel", "Dre", "Sera", "Vela", "Ner", "Reth", "Mora", "Bal",
                "Thal", "Aran", "Sadr", "Vand", "Oth", "Dral", "Ind", "Feln")
FAMILY_ENDINGS = ("vayn", "salen", "dren", "rith", "vani", "endas", "reth",
                  "veth", "rano", "dral", "myn", "saro")


def generate_names(seed, count):
    """Sample unique full names without consuming the simulation's random stream."""
    given_count = len(GIVEN_ROOTS) * len(GIVEN_ENDINGS)
    family_count = len(FAMILY_ROOTS) * len(FAMILY_ENDINGS)
    rng = random.Random(f"necropolis-names-v1:{seed}")
    names = []
    for index in rng.sample(range(given_count * family_count), count):
        given, family = divmod(index, family_count)
        gr, ge = divmod(given, len(GIVEN_ENDINGS))
        fr, fe = divmod(family, len(FAMILY_ENDINGS))
        names.append(f"{GIVEN_ROOTS[gr]}{GIVEN_ENDINGS[ge]} "
                     f"{FAMILY_ROOTS[fr]}{FAMILY_ENDINGS[fe]}")
    return names
