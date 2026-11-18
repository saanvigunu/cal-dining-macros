"""Parser tests against real Cal Dining snapshots published for 2026-11-16.

The fixture files in data/sample/ are byte-for-byte what Cal Dining served
at https://dining.berkeley.edu/wp-content/uploads/menus-exportimport/ that
day, filenames unchanged. Expected numbers below are the published values,
not targets we chose.
"""

import datetime
import os
import unittest

from caldining.eatec import KNOWN_NUTRIENTS, parse_file, parse_string

SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "sample",
)
CAFE3 = os.path.join(SAMPLE_DIR, "Cafe_3_20261116.xml")
CROSSROADS = os.path.join(SAMPLE_DIR, "Crossroads_20261116.xml")


class ParseFileTests(unittest.TestCase):
    def test_cafe3_meal_periods(self):
        menus = parse_file(CAFE3)
        self.assertEqual([m.meal_period for m in menus],
                         ["Fall - Breakfast", "Fall - Lunch", "Fall - Dinner"])
        for m in menus:
            self.assertEqual(m.location, "Cafe 3")
            self.assertEqual(m.serve_date, datetime.date(2026, 11, 16))

    def test_item_counts(self):
        menus = parse_file(CAFE3)
        self.assertEqual([len(m.recipes) for m in menus], [39, 54, 54])

    def test_meal_times(self):
        breakfast = parse_file(CAFE3)[0]
        self.assertEqual(breakfast.start_time, "07:00")
        self.assertEqual(breakfast.end_time, "10:00")

    def test_menu_name_kept_verbatim(self):
        # The published breakfast name really does end in a stray "choriz";
        # the parser must not clean vendor text.
        breakfast = parse_file(CAFE3)[0]
        self.assertEqual(
            breakfast.name,
            "Cafe 3 Fall 26 Breakfast 08/25/26 - 12/18/26choriz",
        )

    def test_nutrient_columns_match_published_header(self):
        breakfast = parse_file(CAFE3)[0]
        self.assertEqual(list(breakfast.recipes[0].nutrients.keys()),
                         KNOWN_NUTRIENTS)

    def test_published_values_scrambled_eggs(self):
        breakfast = parse_file(CAFE3)[0]
        eggs = next(r for r in breakfast.recipes if r.name == "Scrambled Eggs")
        self.assertEqual(eggs.serving_size, 3.93)
        self.assertEqual(eggs.serving_unit, "oz")
        self.assertAlmostEqual(eggs.macro("Calories (kcal)"), 184.98)
        self.assertAlmostEqual(eggs.macro("Protein (g)"), 13.92)
        self.assertAlmostEqual(eggs.macro("Carbohydrate (g)"), 2.32)
        self.assertAlmostEqual(eggs.macro("Total Lipid/Fat (g)"), 12.88)
        self.assertTrue(eggs.approved_nutrition)
        self.assertEqual(eggs.allergens, ["Egg"])
        self.assertEqual(eggs.dietary, ["Vegetarian Option"])
        self.assertIn("Cage Free Whole Eggs", eggs.ingredients)

    def test_crossroads_parses(self):
        menus = parse_file(CROSSROADS)
        self.assertEqual([len(m.recipes) for m in menus], [17, 66, 72])
        self.assertEqual(menus[0].location, "Crossroads")

    def test_same_item_same_numbers_across_halls(self):
        cafe = parse_file(CAFE3)[0]
        xrds = parse_file(CROSSROADS)[0]
        a = next(r for r in cafe.recipes if r.name == "Scrambled Eggs")
        b = next(r for r in xrds.recipes if r.name == "Scrambled Eggs")
        self.assertEqual(a.nutrients, b.nutrients)


class RobustnessTests(unittest.TestCase):
    def test_rejects_non_eatec(self):
        with self.assertRaises(ValueError):
            parse_string("<html><body>nope</body></html>")

    def test_missing_nutrient_value_is_none_not_zero(self):
        xml = """<EatecExchange>
          <menu id="1" name="Test 01/01/26 - 01/02/26" servedate="20261116"
                location="Cafe 3" mealperiodname="Fall - Breakfast"
                mealstarttime="07:00" mealendtime="10:00">
            <nutrients>Calories (kcal)|Protein (g)|</nutrients>
            <recipes>
              <recipe id="1" category="Test" description="d" shortName="Mystery"
                      servingSize="1" servingSizeUnit="oz" servingDescription="1 SV"
                      approvedNutrition="No" nutrients="|5|">
                <allergens><allergen id="Egg">No</allergen></allergens>
                <dietaryChoices/>
              </recipe>
            </recipes>
          </menu>
        </EatecExchange>"""
        (menu,) = parse_string(xml)
        (recipe,) = menu.recipes
        self.assertIsNone(recipe.macro("Calories (kcal)"))
        self.assertAlmostEqual(recipe.macro("Protein (g)"), 5.0)
        self.assertFalse(recipe.approved_nutrition)
        self.assertEqual(recipe.allergens, [])

    def test_bad_servedate_raises(self):
        xml = """<EatecExchange>
          <menu id="1" name="m" servedate="16/11/2026" location="Cafe 3"
                mealperiodname="Fall - Breakfast">
            <nutrients>Calories (kcal)|</nutrients>
            <recipes/>
          </menu>
        </EatecExchange>"""
        with self.assertRaises(ValueError):
            parse_string(xml)


if __name__ == "__main__":
    unittest.main()
