import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from monolith import app as app_module
from monolith import database
from monolith import recipe_api
from monolith.recipe_api import RecipeServiceError


class MealPlanDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = (
            Path(self.temporary_directory.name) / "monolith.db"
        )
        database.init_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_items_can_be_created_checked_and_deleted(self):
        entry_id = database.create_meal_plan_item(
            "2026-09-28",
            "Gemüsecurry",
        )

        items = database.get_meal_plan_items(["2026-09-28"])
        self.assertEqual(items[0]["name"], "Gemüsecurry")
        self.assertFalse(items[0]["checked"])

        self.assertTrue(
            database.set_meal_plan_item_checked(entry_id, True)
        )
        items = database.get_meal_plan_items(["2026-09-28"])
        self.assertTrue(items[0]["checked"])

        self.assertTrue(database.delete_meal_plan_item(entry_id))
        self.assertEqual(
            database.get_meal_plan_items(["2026-09-28"]),
            [],
        )


class MealPlanApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = (
            Path(self.temporary_directory.name) / "monolith.db"
        )
        database.init_database()
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_full_meal_plan_api_lifecycle(self):
        create_response = self.client.post(
            "/api/meal-plan/items",
            json={
                "name": "Ofengemüse",
                "week_offset": 0,
            },
        )
        self.assertEqual(create_response.status_code, 201)
        entry_id = create_response.get_json()["entry_id"]

        data = self.client.get("/api/meal-plan").get_json()
        self.assertEqual(data["weeks"][0]["items"][0]["name"], "Ofengemüse")

        move_response = self.client.put(
            f"/api/meal-plan/items/{entry_id}",
            json={"week_offset": 1},
        )
        self.assertEqual(move_response.status_code, 200)
        moved_data = self.client.get("/api/meal-plan").get_json()
        self.assertEqual(moved_data["weeks"][0]["items"], [])
        self.assertEqual(
            moved_data["weeks"][1]["items"][0]["name"],
            "Ofengemüse",
        )

        update_response = self.client.put(
            f"/api/meal-plan/items/{entry_id}",
            json={"checked": True},
        )
        self.assertEqual(update_response.status_code, 200)
        checked_data = self.client.get("/api/meal-plan").get_json()
        self.assertEqual(checked_data["weeks"][1]["items"], [])

        delete_response = self.client.delete(
            f"/api/meal-plan/items/{entry_id}"
        )
        self.assertEqual(delete_response.status_code, 200)

    def test_invalid_items_are_rejected(self):
        self.assertEqual(
            self.client.post(
                "/api/meal-plan/items",
                json={"name": "", "week_offset": 0},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/meal-plan/items",
                json={"name": "Pizza", "week_offset": 2},
            ).status_code,
            400,
        )

    @patch("monolith.app.fetch_random_recipe")
    def test_random_recipe_is_returned(self, fetch_mock):
        fetch_mock.return_value = {
            "id": "1",
            "title": "Testgericht",
            "category": "Vegetarian",
            "area": "German",
            "image_url": "https://example.test/meal.jpg",
            "instructions": "Kochen.",
            "source_url": "",
            "video_url": "",
            "ingredients": [
                {"name": "Kartoffeln", "measure": "500 g"},
            ],
        }

        response = self.client.get("/api/meal-plan/random-recipe")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["recipe"]["title"],
            "Testgericht",
        )

    @patch("monolith.app.fetch_random_recipe")
    def test_random_recipe_error_is_reported(self, fetch_mock):
        fetch_mock.side_effect = RecipeServiceError("Nicht erreichbar")
        response = self.client.get("/api/meal-plan/random-recipe")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "Nicht erreichbar")

    def test_recipe_bookmarks_can_be_saved_and_deleted(self):
        recipe = {
            "id": "huggingface-42",
            "source_id": "huggingface-42",
            "title": "Kartoffelsuppe",
            "category": "Hauptgericht",
            "area": "Chefkoch-Datensatz",
            "image_url": "",
            "instructions": "Kartoffeln kochen und pürieren.",
            "source_url": "https://example.test/rezept",
            "video_url": "",
            "ingredients": [
                {"name": "Kartoffeln", "measure": "1 kg"},
            ],
        }

        save_response = self.client.post(
            "/api/meal-plan/bookmarks",
            json={"recipe": recipe},
        )
        self.assertEqual(save_response.status_code, 201)
        bookmark_id = save_response.get_json()["bookmark_id"]

        bookmarks = self.client.get(
            "/api/meal-plan/bookmarks"
        ).get_json()["recipes"]
        self.assertEqual(bookmarks[0]["title"], "Kartoffelsuppe")

        delete_response = self.client.delete(
            f"/api/meal-plan/bookmarks/{bookmark_id}"
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            self.client.get("/api/meal-plan/bookmarks")
            .get_json()["recipes"],
            [],
        )


class RecipeApiTests(unittest.TestCase):
    @patch("monolith.recipe_api.requests.get")
    @patch("monolith.recipe_api.secrets.randbelow", return_value=42)
    def test_german_dataset_recipe_is_normalized(
        self,
        _random_mock,
        get_mock,
    ):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "rows": [
                {
                    "row_idx": 42,
                    "row": {
                        "name": "Kartoffelsuppe",
                        "instructions": "Alles kochen.",
                        "ingredients": ["1 kg Kartoffeln", "Salz"],
                        "url": "https://www.chefkoch.de/rezepte/42/",
                    },
                },
            ],
        }
        image_response = Mock()
        image_response.raise_for_status.return_value = None
        image_response.headers = {
            "Content-Type": "text/html; charset=utf-8",
        }
        image_response.text = (
            '<html><head><meta property="og:image" '
            'content="https://img.chefkoch-cdn.de/rezept.jpg">'
            '</head></html>'
        )
        get_mock.side_effect = [response, image_response]

        recipe = recipe_api.fetch_random_recipe()

        self.assertEqual(recipe["title"], "Kartoffelsuppe")
        self.assertEqual(recipe["source_id"], "huggingface-42")
        self.assertEqual(recipe["ingredients"][0]["name"], "1 kg Kartoffeln")
        self.assertEqual(
            recipe["image_url"],
            "https://img.chefkoch-cdn.de/rezept.jpg",
        )
        self.assertEqual(
            get_mock.call_args_list[0].kwargs["params"]["offset"],
            42,
        )

    @patch("monolith.recipe_api.requests.get")
    def test_recipe_stays_available_when_image_lookup_fails(self, get_mock):
        dataset_response = Mock()
        dataset_response.raise_for_status.return_value = None
        dataset_response.json.return_value = {
            "rows": [{
                "row_idx": 7,
                "row": {
                    "name": "Curry",
                    "instructions": "Alles kochen.",
                    "ingredients": ["Linsen"],
                    "url": "https://www.chefkoch.de/rezepte/7/",
                },
            }],
        }
        get_mock.side_effect = [
            dataset_response,
            recipe_api.requests.RequestException(),
        ]

        recipe = recipe_api.fetch_random_recipe()

        self.assertEqual(recipe["title"], "Curry")
        self.assertEqual(recipe["image_url"], "")

    @patch("monolith.recipe_api.requests.get")
    def test_local_german_fallback_is_used_on_network_error(self, get_mock):
        get_mock.side_effect = recipe_api.requests.RequestException()
        recipe = recipe_api.fetch_random_recipe()
        self.assertTrue(recipe["title"])
        self.assertTrue(recipe["instructions"])
        self.assertTrue(recipe["ingredients"])


if __name__ == "__main__":
    unittest.main()
