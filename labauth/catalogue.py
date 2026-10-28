"""Every permission a community can give, grouped by app, and the platform permissions only the superuser gives.

A community permission is held *in one community*: what a user may do in community A says nothing about community B.
Each app has a `<app>.view` code that opens the app; its other codes only count when `view` is held too.
A new house app adds a block to APPS (and a tile on Home, `portal/apps.py`).
"""

APPS = [
    {
        "app": "shopping",
        "name": "Shopping",
        "perms": [
            ("shopping.view", "Open Shopping", "Prices, promotions, compare; your own stars, seen marks and savings; read the community's lists."),
            ("shopping.lists.edit", "Edit lists", "Create, change and delete the community's shopping lists."),
        ],
    },
    {
        "app": "nyochi",
        "name": "Nyochi",
        "perms": [
            ("nyochi.view", "Open Nyochi", "Read the community's recipes, ingredients, shops, plan and saved lists."),
            ("nyochi.recipes.edit", "Edit recipes", "Recipes and tags."),
            ("nyochi.ingredients.edit", "Edit ingredients", "Ingredients, seasons, categories and Shopping links."),
            ("nyochi.shops.edit", "Edit shops", "Shops, locations, aisles and layouts."),
            ("nyochi.lists.edit", "Edit lists", "The plan and the saved grocery lists."),
        ],
    },
]

# Global: they act on data every community shares (the stores' catalogues), so only the superuser gives them, per user.
PLATFORM = [
    ("shopping.fetch", "Shopping: Fetch", "Start and cancel fetches, paste Colruyt's cookie, manage schedules."),
    ("shopping.datasets", "Shopping: Datasets", "Rename, delete, import and download datasets and the database backup."),
]

COMMUNITY_PERMS = [code for block in APPS for code, _, _ in block["perms"]]
PLATFORM_PERMS = [code for code, _, _ in PLATFORM]
LABELS = {code: label for block in APPS for code, label, _ in block["perms"]} | {code: label for code, label, _ in PLATFORM}


def app_of(code):
    return code.split(".", 1)[0]


def view_code(app):
    return f"{app}.view"


def is_known(code):
    return code in COMMUNITY_PERMS
