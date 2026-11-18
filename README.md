# cal-dining-macros

A command-line tool for planning a dining-hall plate at UC Berkeley: pick
items off the day's Cal Dining menu, scale servings, and see the macro
totals - calories, protein, carbs, fat, fiber, sugar, sodium.

## Where the numbers come from

Every value is Cal Dining's own published nutrition data. Cal Dining posts
one XML file per location per day (the same exports that power
[dining.berkeley.edu/menus](https://dining.berkeley.edu/menus/)):

```
https://dining.berkeley.edu/wp-content/uploads/menus-exportimport/{Location}_{YYYYMMDD}.xml
```

Each file carries its serve date, meal periods, and the menu's validity
window, and the tool keeps all three attached to whatever it prints. Nothing
is estimated: if a nutrient is blank in the published file, the tool shows
`-` and leaves it out of the totals (and says so), instead of inventing a
number. Each item also keeps the vendor's `approvedNutrition` flag, and the
plate summary warns when an item doesn't have it.

Portions in a dining hall are served by people, not scales, so treat the
numbers as the published per-serving values they are - not a lab measurement
of your actual plate. Not medical or dietary advice.

## Usage

No dependencies beyond Python 3.10+.

```bash
# download a day's published menu into ./data
python3 -m caldining fetch --location Cafe_3 --date 20261116

# see the menu with per-item macros
python3 -m caldining menu --location Cafe_3 --date 20261116 --meal lunch

# sum a plate ("x2" scales servings)
python3 -m caldining plate --location Cafe_3 --date 20261116 --meal lunch \
    "Halal Herb Roasted Chicken Thigh" "Brown Rice x2" "Sauteed Carrots Squash and Red Pepper"
```

Example plate output:

```
+ Halal Herb Roasted Chicken Thigh x1 (4 oz each)
+ Brown Rice x2 (4 oz each)
+ Sauteed Carrots Squash and Red Pepper x1 (4.19 oz each)

plate totals:
  cal      561
  protein  30
  carbs    68
  fat      18
  fiber    5
  sugar    4
  sodium   476

source: Cal Dining published menu XML for Cafe_3, served 2026-11-16
menu:   Cafe 3 Fall 26 Lunch 08/25/26 - 12/18/26 (Fall - Lunch, 11:00-15:00)
```

Locations: `Cafe_3`, `Crossroads`, `Clark_Kerr_Campus`, `Foothill`,
`Bear_Market`, `Cub_Market`, `Den`, `Eateries_at_the_Student_Union`,
`Gateway_Cafe`, `Golden_Bear_Cafe`, `Local_x_Design`, `Qualcomm_Cafe`.

`menu` and `plate` read the local dated snapshots, so re-running a past date
shows what was actually published for that date, not whatever is online now.
The snapshots in `data/sample/` (Cafe 3 and Crossroads, 2026-11-16) are real
published files, kept with their original names, and the tests run against
them.

## What it doesn't do

- No live scraping at meal time - you `fetch` a day first, then work offline.
- No estimates for items the vendor leaves blank.
- No ingredient-level allergen math beyond the vendor's own allergen flags
  (which the parser preserves). If you have an allergy, treat the dining
  hall's signage and staff as the authority, not this tool.

## Tests

```bash
python3 -m unittest discover -s tests
```

25 tests: parser behavior on the real snapshots (including preserving a
vendor typo in a menu name verbatim), missing-value handling, plate math,
and name resolution.

## Why I built it

I live on the meal plan, and "what should I eat at Crossroads tonight" is a
real daily question. I wanted to answer it with the dining hall's own
numbers, dated and honest about what they cover - not a generic calorie
database that's never seen a Cafe 3 chilaquile.
