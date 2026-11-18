"""Plate and name-resolution tests, on the real 2026-11-16 snapshots."""

import os
import unittest

from caldining.eatec import parse_file
from caldining.planner import Plate, find_recipe, parse_pick

SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "sample",
)
CAFE3 = os.path.join(SAMPLE_DIR, "Cafe_3_20261116.xml")


def breakfast():
    return parse_file(CAFE3)[0]


class FindRecipeTests(unittest.TestCase):
    def test_exact_match(self):
        menu = breakfast()
        r = find_recipe(menu.recipes, "scrambled eggs")
        self.assertEqual(r.name, "Scrambled Eggs")

    def test_unique_substring(self):
        menu = breakfast()
        r = find_recipe(menu.recipes, "chilaquiles")
        self.assertIn("Chilaquiles", r.name)

    def test_ambiguous_lists_candidates(self):
        menu = breakfast()
        with self.assertRaises(ValueError) as ctx:
            find_recipe(menu.recipes, "bagel")
        self.assertIn("ambiguous", str(ctx.exception))

    def test_miss(self):
        menu = breakfast()
        with self.assertRaises(ValueError):
            find_recipe(menu.recipes, "lobster thermidor")


class ParsePickTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_pick("Brown Rice"), ("Brown Rice", 1.0))

    def test_multiplier(self):
        self.assertEqual(parse_pick("Brown Rice x2"), ("Brown Rice", 2.0))

    def test_fractional(self):
        self.assertEqual(parse_pick("Oatmeal x0.5"), ("Oatmeal", 0.5))

    def test_x_inside_name_kept(self):
        self.assertEqual(parse_pick("Fried Tater Tots"), ("Fried Tater Tots", 1.0))


class PlateTotalsTests(unittest.TestCase):
    def test_single_item_matches_published(self):
        menu = breakfast()
        plate = Plate()
        plate.add(find_recipe(menu.recipes, "Scrambled Eggs"))
        totals = plate.totals()
        self.assertAlmostEqual(totals["Calories (kcal)"], 184.98)
        self.assertAlmostEqual(totals["Protein (g)"], 13.92)

    def test_servings_multiplier(self):
        menu = breakfast()
        plate = Plate()
        plate.add(find_recipe(menu.recipes, "Scrambled Eggs"), servings=2)
        self.assertAlmostEqual(plate.totals()["Calories (kcal)"], 184.98 * 2)

    def test_two_items_sum(self):
        menu = breakfast()
        eggs = find_recipe(menu.recipes, "Scrambled Eggs")
        rice = find_recipe(menu.recipes, "Brown Rice")
        plate = Plate()
        plate.add(eggs)
        plate.add(rice)
        expected = eggs.macro("Calories (kcal)") + rice.macro("Calories (kcal)")
        self.assertAlmostEqual(plate.totals()["Calories (kcal)"], expected)

    def test_rejects_nonpositive_servings(self):
        menu = breakfast()
        plate = Plate()
        with self.assertRaises(ValueError):
            plate.add(find_recipe(menu.recipes, "Oatmeal"), servings=0)

    def test_missing_values_excluded_and_reported(self):
        menu = breakfast()
        recipe = find_recipe(menu.recipes, "Oatmeal")
        recipe.nutrients["Protein (g)"] = None  # simulate an unpublished field
        plate = Plate()
        plate.add(recipe)
        self.assertIsNone(plate.totals()["Protein (g)"])
        self.assertEqual(plate.gaps()["Protein (g)"], ["Oatmeal"])

    def test_unapproved_flagged(self):
        menu = breakfast()
        recipe = find_recipe(menu.recipes, "Oatmeal")
        recipe.approved_nutrition = False
        plate = Plate()
        plate.add(recipe)
        self.assertEqual(plate.unapproved(), ["Oatmeal"])


if __name__ == "__main__":
    unittest.main()
