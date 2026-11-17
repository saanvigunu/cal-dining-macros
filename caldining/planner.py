"""Plate building and macro totals.

A Plate is a list of (recipe, servings) picks from one day's published menus.
Totals only ever add up numbers Cal Dining published. When an item is missing
a nutrient, that item contributes nothing for that nutrient and the gap is
reported - totals are never silently padded with guesses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .eatec import Recipe

#: The columns a macro total reports on, in display order.
MACRO_COLUMNS = [
    "Calories (kcal)",
    "Protein (g)",
    "Carbohydrate (g)",
    "Total Lipid/Fat (g)",
    "Total Dietary Fiber (g)",
    "Sugar (g)",
    "Sodium (mg)",
]


@dataclass
class PlateItem:
    recipe: Recipe
    servings: float = 1.0  # multiplier on the published serving size


@dataclass
class Plate:
    items: list[PlateItem] = field(default_factory=list)

    def add(self, recipe: Recipe, servings: float = 1.0) -> None:
        if servings <= 0:
            raise ValueError("servings must be positive")
        self.items.append(PlateItem(recipe, servings))

    def totals(self) -> dict[str, float | None]:
        """Sum each macro column over the plate.

        A column total is the sum of the published values present, or None if
        no item has a value for it. Use gaps() to see what was left out.
        """
        out: dict[str, float | None] = {}
        for col in MACRO_COLUMNS:
            vals = [
                item.recipe.nutrients.get(col) * item.servings
                for item in self.items
                if item.recipe.nutrients.get(col) is not None
            ]
            out[col] = sum(vals) if vals else None
        return out

    def gaps(self) -> dict[str, list[str]]:
        """Which items lack a published value for each macro column."""
        out: dict[str, list[str]] = {}
        for col in MACRO_COLUMNS:
            missing = [
                item.recipe.name
                for item in self.items
                if item.recipe.nutrients.get(col) is None
            ]
            if missing:
                out[col] = missing
        return out

    def unapproved(self) -> list[str]:
        """Items the vendor did not mark approvedNutrition=Yes."""
        return [i.recipe.name for i in self.items if not i.recipe.approved_nutrition]


def find_recipe(recipes: list[Recipe], query: str) -> Recipe:
    """Resolve a user-typed name to one recipe.

    Exact (case-insensitive) match wins, then a unique substring match.
    Ambiguity and misses are errors that list candidates - picking silently
    would put the wrong published numbers on someone's plate.
    """
    q = query.strip().lower()
    if not q:
        raise ValueError("empty item name")

    exact = [r for r in recipes if r.name.strip().lower() == q]
    if len(exact) == 1:
        return exact[0]

    partial = [r for r in recipes if q in r.name.strip().lower()]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise ValueError(f"no item matching {query!r} on this menu")
    names = ", ".join(sorted(r.name.strip() for r in partial))
    raise ValueError(f"{query!r} is ambiguous: {names}")


def parse_pick(spec: str) -> tuple[str, float]:
    """Split a pick like 'Brown Rice x2' into (name, servings)."""
    name, _, mult = spec.rpartition(" x")
    if name and mult:
        try:
            return name.strip(), float(mult)
        except ValueError:
            pass
    return spec.strip(), 1.0
