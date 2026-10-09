import secrets
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests


DATASET_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DATASET_NAME = "SinclairSchneider/deutsche_rezepte"
DATASET_TOTAL_ROWS = 12190
REQUEST_TIMEOUT_SECONDS = 8
IMAGE_METADATA_TIMEOUT_SECONDS = 5
IMAGE_METADATA_MAX_CHARS = 750000


class RecipeServiceError(RuntimeError):
    pass


class _RecipeImageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image_url = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta" or self.image_url:
            return

        values = {
            str(name).lower(): value
            for name, value in attrs
            if name and value
        }
        property_name = str(
            values.get("property") or values.get("name") or ""
        ).lower()
        if property_name in {"og:image", "og:image:secure_url"}:
            self.image_url = unescape(
                str(values.get("content") or "")
            ).strip()


FALLBACK_RECIPES = [
    {
        "id": "fallback-spaghetti-bolognese",
        "title": "Spaghetti Bolognese",
        "ingredients": [
            {"name": "Spaghetti", "measure": "400 g"},
            {"name": "Rinderhackfleisch", "measure": "500 g"},
            {"name": "Gehackte Tomaten", "measure": "800 g"},
            {"name": "Zwiebel", "measure": "1"},
            {"name": "Knoblauchzehen", "measure": "2"},
            {"name": "Tomatenmark", "measure": "2 EL"},
            {"name": "Olivenöl", "measure": "2 EL"},
            {"name": "Salz, Pfeffer und Oregano", "measure": "nach Geschmack"},
        ],
        "instructions": (
            "Zwiebel und Knoblauch fein würfeln und im Olivenöl glasig braten. "
            "Das Hackfleisch dazugeben und krümelig anbraten. Tomatenmark kurz "
            "mitrösten, anschließend die gehackten Tomaten einrühren. Mit Salz, "
            "Pfeffer und Oregano würzen und etwa 25 Minuten köcheln lassen. "
            "Währenddessen die Spaghetti nach Packungsangabe kochen und mit der "
            "Sauce servieren."
        ),
    },
    {
        "id": "fallback-kartoffelauflauf",
        "title": "Kartoffelauflauf mit Gemüse",
        "ingredients": [
            {"name": "Kartoffeln", "measure": "800 g"},
            {"name": "Paprika", "measure": "2"},
            {"name": "Zucchini", "measure": "1"},
            {"name": "Sahne", "measure": "250 ml"},
            {"name": "Geriebener Käse", "measure": "150 g"},
            {"name": "Knoblauchzehe", "measure": "1"},
            {"name": "Salz, Pfeffer und Muskat", "measure": "nach Geschmack"},
        ],
        "instructions": (
            "Kartoffeln schälen, in dünne Scheiben schneiden und zehn Minuten "
            "vorkochen. Paprika und Zucchini klein schneiden. Alles in eine "
            "Auflaufform geben. Sahne mit Knoblauch, Salz, Pfeffer und Muskat "
            "verrühren und darüber gießen. Mit Käse bestreuen und bei 190 Grad "
            "etwa 35 Minuten backen."
        ),
    },
    {
        "id": "fallback-haehnchenpfanne",
        "title": "Hähnchen-Gemüse-Pfanne mit Reis",
        "ingredients": [
            {"name": "Hähnchenbrust", "measure": "500 g"},
            {"name": "Reis", "measure": "250 g"},
            {"name": "Paprika", "measure": "2"},
            {"name": "Brokkoli", "measure": "1 kleiner Kopf"},
            {"name": "Zwiebel", "measure": "1"},
            {"name": "Gemüsebrühe", "measure": "200 ml"},
            {"name": "Paprikapulver, Salz und Pfeffer", "measure": "nach Geschmack"},
        ],
        "instructions": (
            "Den Reis kochen. Hähnchenbrust in Stücke schneiden, würzen und in "
            "einer großen Pfanne anbraten. Zwiebel, Paprika und Brokkoli "
            "hinzugeben und fünf Minuten mitbraten. Mit Gemüsebrühe ablöschen "
            "und zugedeckt etwa zehn Minuten garen. Mit dem Reis servieren."
        ),
    },
    {
        "id": "fallback-linsencurry",
        "title": "Cremiges Linsencurry",
        "ingredients": [
            {"name": "Rote Linsen", "measure": "250 g"},
            {"name": "Kokosmilch", "measure": "400 ml"},
            {"name": "Gehackte Tomaten", "measure": "400 g"},
            {"name": "Zwiebel", "measure": "1"},
            {"name": "Knoblauchzehen", "measure": "2"},
            {"name": "Currypulver", "measure": "2 TL"},
            {"name": "Gemüsebrühe", "measure": "300 ml"},
            {"name": "Öl und Salz", "measure": "nach Bedarf"},
        ],
        "instructions": (
            "Zwiebel und Knoblauch fein schneiden und in etwas Öl anbraten. "
            "Currypulver kurz mitrösten. Linsen, Tomaten, Kokosmilch und Brühe "
            "zugeben. Alles aufkochen und bei kleiner Hitze etwa 20 Minuten "
            "köcheln lassen, bis die Linsen weich sind. Mit Salz abschmecken."
        ),
    },
]


def _clean(value):
    if not isinstance(value, str):
        return ""
    return value.strip()


def _fallback_recipe():
    recipe = dict(secrets.choice(FALLBACK_RECIPES))
    recipe.update({
        "source_id": recipe["id"],
        "category": "MONOLITH-Klassiker",
        "area": "Deutsch",
        "image_url": "",
        "source_url": "",
        "video_url": "",
    })
    recipe["ingredients"] = [
        dict(ingredient)
        for ingredient in recipe["ingredients"]
    ]
    return recipe


def _is_chefkoch_recipe_url(value):
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"chefkoch.de", "www.chefkoch.de"}
        and parsed.path.startswith("/rezepte/")
    )


@lru_cache(maxsize=256)
def _fetch_recipe_image(source_url):
    if not _is_chefkoch_recipe_url(source_url):
        return ""

    try:
        response = requests.get(
            source_url,
            timeout=IMAGE_METADATA_TIMEOUT_SECONDS,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MONOLITH/1.0)",
                "Accept-Language": "de-DE,de;q=0.9",
            },
        )
        response.raise_for_status()
        content_type = response.headers.get(
            "Content-Type",
            "text/html",
        )
        if "text/html" not in content_type:
            return ""

        parser = _RecipeImageParser()
        parser.feed(response.text[:IMAGE_METADATA_MAX_CHARS])
        image_url = parser.image_url
        parsed_image = urlparse(image_url)
        if parsed_image.scheme != "https" or not parsed_image.netloc:
            return ""
        return image_url
    except (requests.RequestException, ValueError):
        return ""


def _normalize_dataset_recipe(payload):
    rows = payload.get("rows") if isinstance(payload, dict) else None
    entry = rows[0] if isinstance(rows, list) and rows else None
    row = entry.get("row") if isinstance(entry, dict) else None

    if not isinstance(row, dict):
        raise RecipeServiceError(
            "Die Rezeptdatenbank hat kein Gericht geliefert."
        )

    title = _clean(row.get("name") or row.get("Name"))
    instructions = _clean(
        row.get("instructions") or row.get("Instructions")
    )
    raw_ingredients = row.get("ingredients") or row.get("Ingredients")

    if (
        not title
        or not instructions
        or not isinstance(raw_ingredients, list)
    ):
        raise RecipeServiceError(
            "Das geladene Rezept ist unvollständig."
        )

    ingredients = [
        {
            "name": _clean(ingredient),
            "measure": "",
        }
        for ingredient in raw_ingredients
        if _clean(ingredient)
    ]

    if not ingredients:
        raise RecipeServiceError(
            "Das geladene Rezept enthält keine Zutaten."
        )

    row_index = entry.get("row_idx")
    source_url = _clean(row.get("url") or row.get("Url"))
    source_id = f"huggingface-{row_index}"

    return {
        "id": source_id,
        "source_id": source_id,
        "title": title,
        "category": "Deutschsprachiges Rezept",
        "area": "Chefkoch-Datensatz",
        "image_url": "",
        "instructions": instructions,
        "source_url": source_url,
        "video_url": "",
        "ingredients": ingredients,
    }


def fetch_random_recipe():
    offset = secrets.randbelow(DATASET_TOTAL_ROWS)

    try:
        response = requests.get(
            DATASET_ROWS_URL,
            params={
                "dataset": DATASET_NAME,
                "config": "default",
                "split": "train",
                "offset": offset,
                "length": 1,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "MONOLITH/1.0"},
        )
        response.raise_for_status()
        recipe = _normalize_dataset_recipe(response.json())
        recipe["image_url"] = _fetch_recipe_image(recipe["source_url"])
        return recipe
    except (
        requests.RequestException,
        RecipeServiceError,
        ValueError,
    ):
        return _fallback_recipe()
