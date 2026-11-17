"""Command-line interface.

    python3 -m caldining fetch  --location Cafe_3 --date 20261116
    python3 -m caldining menu   --location Cafe_3 --date 20261116 --meal lunch
    python3 -m caldining plate  --location Cafe_3 --date 20261116 --meal lunch \
        "Halal Herb Roasted Chicken Thigh" "Brown Rice x2"

`fetch` downloads the day's published XML into ./data (or --data-dir).
`menu` and `plate` read those local files, so what you analyze is a dated
snapshot, not whatever the site happens to show later.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

from .eatec import Menu, parse_file
from .planner import MACRO_COLUMNS, Plate, find_recipe, parse_pick

BASE_URL = "https://dining.berkeley.edu/wp-content/uploads/menus-exportimport"

#: Filenames observed on the site use underscores and these spellings.
KNOWN_LOCATIONS = [
    "Cafe_3",
    "Crossroads",
    "Clark_Kerr_Campus",
    "Foothill",
    "Bear_Market",
    "Cub_Market",
    "Den",
    "Eateries_at_the_Student_Union",
    "Gateway_Cafe",
    "Golden_Bear_Cafe",
    "Local_x_Design",
    "Qualcomm_Cafe",
]

SHORT_COLUMNS = {
    "Calories (kcal)": "cal",
    "Protein (g)": "protein",
    "Carbohydrate (g)": "carbs",
    "Total Lipid/Fat (g)": "fat",
    "Total Dietary Fiber (g)": "fiber",
    "Sugar (g)": "sugar",
    "Sodium (mg)": "sodium",
}


def _source_url(location: str, date: str) -> str:
    return f"{BASE_URL}/{location}_{date}.xml"


def _local_path(data_dir: str, location: str, date: str) -> str:
    return os.path.join(data_dir, f"{location}_{date}.xml")


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def _pick_menu(menus: list[Menu], meal: str | None) -> Menu:
    if meal is None:
        if len(menus) == 1:
            return menus[0]
        kinds = ", ".join(m.meal_period for m in menus)
        raise SystemExit(f"more than one meal period ({kinds}); pass --meal")
    wanted = meal.strip().lower()
    for m in menus:
        if wanted in m.meal_period.lower():
            return m
    kinds = ", ".join(m.meal_period for m in menus)
    raise SystemExit(f"no meal matching {meal!r}; available: {kinds}")


def _print_provenance(menu: Menu, location: str) -> None:
    print()
    print(f"source: Cal Dining published menu XML for {location}, "
          f"served {menu.serve_date.isoformat()}")
    print(f"menu:   {menu.name} ({menu.meal_period}, {menu.start_time}-{menu.end_time})")
    print("values are Cal Dining's published nutrition facts for that date. "
          "items marked '-' have no published value.")


def cmd_fetch(args: argparse.Namespace) -> int:
    os.makedirs(args.data_dir, exist_ok=True)
    url = _source_url(args.location, args.date)
    dest = _local_path(args.data_dir, args.location, args.date)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            body = resp.read()
    except Exception as exc:  # network and 404s land here
        print(f"fetch failed for {url}: {exc}", file=sys.stderr)
        return 1
    if not body.startswith(b"<EatecExchange"):
        print(f"unexpected content from {url}; not saving", file=sys.stderr)
        return 1
    with open(dest, "wb") as fh:
        fh.write(body)
    print(f"saved {dest} ({len(body)} bytes)")
    return 0


def _load(args: argparse.Namespace) -> Menu:
    path = _local_path(args.data_dir, args.location, args.date)
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found; run `fetch` first")
    return _pick_menu(parse_file(path), args.meal)


def cmd_menu(args: argparse.Namespace) -> int:
    menu = _load(args)
    print(f"{menu.location} - {menu.meal_period} - {menu.serve_date.isoformat()}")
    print(f"{'item':<48} {'cal':>5} {'protein':>7} {'carbs':>6} {'fat':>5}")
    station = None
    for r in menu.recipes:
        if r.category != station:
            station = r.category
            print(f"\n[{station}]")
        cal = r.macro("Calories (kcal)")
        pro = r.macro("Protein (g)")
        carb = r.macro("Carbohydrate (g)")
        fat = r.macro("Total Lipid/Fat (g)")
        size = f"{r.serving_size:g} {r.serving_unit}" if r.serving_size else ""
        print(f"{r.name[:46]:<48} {_fmt(cal):>5} {_fmt(pro):>7} {_fmt(carb):>6} {_fmt(fat):>5}  {size}")
    _print_provenance(menu, args.location)
    return 0


def cmd_plate(args: argparse.Namespace) -> int:
    menu = _load(args)
    plate = Plate()
    for spec in args.items:
        name, servings = parse_pick(spec)
        try:
            recipe = find_recipe(menu.recipes, name)
        except ValueError as exc:
            raise SystemExit(str(exc))
        plate.add(recipe, servings)
        size = f"{recipe.serving_size:g} {recipe.serving_unit}" if recipe.serving_size else ""
        print(f"+ {recipe.name} x{servings:g} ({size} each)")

    totals = plate.totals()
    print("\nplate totals:")
    for col in MACRO_COLUMNS:
        print(f"  {SHORT_COLUMNS[col]:<8} {_fmt(totals[col])}")

    gaps = plate.gaps()
    if gaps:
        print("\nnot published for every item (excluded from totals):")
        for col, names in gaps.items():
            print(f"  {SHORT_COLUMNS[col]}: missing for {', '.join(names)}")
    unapproved = plate.unapproved()
    if unapproved:
        print("\nvendor did not mark approvedNutrition=Yes: " + ", ".join(unapproved))
    _print_provenance(menu, args.location)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="caldining",
        description="Plan dining-hall plates from Cal Dining's published menus.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--data-dir", default="data",
                       help="where dated menu XML snapshots live (default ./data)")
        p.add_argument("--location", required=True,
                       help="file-style name, e.g. Cafe_3 (see KNOWN_LOCATIONS)")
        p.add_argument("--date", required=True, help="serve date, YYYYMMDD")

    p_fetch = sub.add_parser("fetch", help="download a day's published menu XML")
    common(p_fetch)
    p_fetch.set_defaults(func=cmd_fetch)

    p_menu = sub.add_parser("menu", help="list items with their published macros")
    common(p_menu)
    p_menu.add_argument("--meal", help="breakfast, lunch or dinner (substring ok)")
    p_menu.set_defaults(func=cmd_menu)

    p_plate = sub.add_parser("plate", help="sum macros for a set of picks")
    common(p_plate)
    p_plate.add_argument("--meal", help="breakfast, lunch or dinner (substring ok)")
    p_plate.add_argument("items", nargs="+",
                         help="'Item Name' or 'Item Name xN' for N servings")
    p_plate.set_defaults(func=cmd_plate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
