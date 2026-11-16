"""Parser for Cal Dining's EatecExchange menu exports.

Cal Dining publishes one XML file per location per day:

    https://dining.berkeley.edu/wp-content/uploads/menus-exportimport/{Location}_{YYYYMMDD}.xml

(for example Cafe_3_20261116.xml). These are the same files that power
https://dining.berkeley.edu/menus/ - the site's menu items carry the file
path in a data attribute.

Every value this module returns comes straight from those files. Nothing is
estimated, rounded, or filled in: a nutrient the file leaves blank comes back
as None, and vendor text (including the occasional typo in a menu name) is
kept verbatim.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from xml.etree import ElementTree as _ET

#: Nutrient columns as published in the files' own <nutrients> header, in order.
#: Parsed per file at parse time; this constant is only documentation.
KNOWN_NUTRIENTS = [
    "Calories (kcal)",
    "Total Lipid/Fat (g)",
    "Saturated fatty acid (g)",
    "Trans Fat (g)",
    "Cholesterol (mg)",
    "Sodium (mg)",
    "Carbohydrate (g)",
    "Total Dietary Fiber (g)",
    "Sugar (g)",
    "Protein (g)",
    "Vitamin A (iu)",
    "Vitamin C (mg)",
    "Calcium (mg)",
    "Iron (mg)",
    "Water (g)",
    "Ash (g)",
    "Vitamin A (rae)",
    "Potassium (mg)",
    "Vitamin D(iu)",
    "Carbon Footprint (kg CO2)",
]


@dataclass
class Recipe:
    """One published menu item. nutrients maps the file's own column names to
    floats, or None where the file has no value for that nutrient."""

    id: str
    category: str  # station, e.g. "Center Plate"
    name: str  # shortName as published
    description: str  # full description as published
    serving_size: float | None
    serving_unit: str
    serving_description: str
    approved_nutrition: bool  # vendor's own approvedNutrition flag
    nutrients: dict[str, float | None]
    allergens: list[str] = field(default_factory=list)  # only the "Yes" ones
    dietary: list[str] = field(default_factory=list)  # Vegan Option, Halal, ...
    ingredients: str = ""

    def macro(self, column: str) -> float | None:
        return self.nutrients.get(column)


@dataclass
class Menu:
    """One meal period at one location on one serve date."""

    id: str
    name: str  # vendor menu name, verbatim (includes its date window)
    location: str
    meal_period: str
    serve_date: _dt.date
    start_time: str
    end_time: str
    recipes: list[Recipe] = field(default_factory=list)


def _split_pipes(raw: str) -> list[str]:
    """Split a pipe-delimited cell, dropping the trailing empty field."""
    parts = raw.split("|")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def _to_float(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None  # non-numeric vendor text is kept out, never guessed


def _parse_recipe(el: _ET.Element, columns: list[str]) -> Recipe:
    values = _split_pipes(el.get("nutrients", ""))
    nutrients: dict[str, float | None] = {}
    for i, col in enumerate(columns):
        nutrients[col] = _to_float(values[i]) if i < len(values) else None

    allergens = [
        a.get("id", "")
        for a in el.findall("./allergens/allergen")
        if (a.text or "").strip().lower() == "yes"
    ]
    dietary = [
        d.get("id", "")
        for d in el.findall("./dietaryChoices/dietaryChoice")
        if (d.text or "").strip().lower() == "yes"
    ]
    ingredients_el = el.find("ingredients")

    serving_raw = el.get("servingSize", "").strip()
    try:
        serving_size: float | None = float(serving_raw)
    except ValueError:
        serving_size = None

    return Recipe(
        id=el.get("id", ""),
        category=el.get("category", ""),
        name=el.get("shortName", "").strip(),
        description=el.get("description", ""),
        serving_size=serving_size,
        serving_unit=el.get("servingSizeUnit", ""),
        serving_description=el.get("servingDescription", ""),
        approved_nutrition=el.get("approvedNutrition", "").strip().lower() == "yes",
        nutrients=nutrients,
        allergens=allergens,
        dietary=dietary,
        ingredients=(ingredients_el.text or "").strip() if ingredients_el is not None else "",
    )


def parse_string(xml_text: str) -> list[Menu]:
    """Parse one EatecExchange document into its meal-period menus."""
    root = _ET.fromstring(xml_text)
    if root.tag != "EatecExchange":
        raise ValueError(f"not an EatecExchange document: <{root.tag}>")

    menus: list[Menu] = []
    for menu_el in root.findall("menu"):
        header = menu_el.findtext("nutrients", default="")
        columns = _split_pipes(header)
        if not columns:
            raise ValueError(f"menu {menu_el.get('id')}: missing <nutrients> header")

        raw_date = menu_el.get("servedate", "")
        try:
            serve_date = _dt.datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError:
            raise ValueError(f"menu {menu_el.get('id')}: bad servedate {raw_date!r}")

        menus.append(
            Menu(
                id=menu_el.get("id", ""),
                name=menu_el.get("name", ""),
                location=menu_el.get("location", ""),
                meal_period=menu_el.get("mealperiodname", ""),
                serve_date=serve_date,
                start_time=menu_el.get("mealstarttime", ""),
                end_time=menu_el.get("mealendtime", ""),
                recipes=[
                    _parse_recipe(r, columns)
                    for r in menu_el.findall("./recipes/recipe")
                ],
            )
        )
    return menus


def parse_file(path: str) -> list[Menu]:
    with open(path, "r", encoding="utf-8") as fh:
        return parse_string(fh.read())
