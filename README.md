# Nyochi — Recipe Book

A personal recipe planner with grocery list generation, ingredient seasonality tracking, and multi-user sharing. Built with Django 6 and HTMX.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 6 (Python 3.12) |
| Database | SQLite (file at `db/db.sqlite3`) |
| Frontend | Tailwind CSS (CDN), HTMX 2.0 |
| Auth | Django built-in auth (`django.contrib.auth`) |

No build step required — Tailwind and HTMX are loaded from CDN.

---

## Features

### Recipes
- Create, edit, and delete recipes with name, description, prep/cook time, difficulty (Easy → Pro), and meal type (Breakfast, Full meal, Snack, Dessert)
- Attach ingredients with quantity, unit, and an optional **main ingredient** flag
- Tag recipes for filtering
- View seasonal availability of each ingredient at a glance from the recipe detail page

### Ingredients
- Full ingredient catalogue with category (Vegetable, Fruit, Starch, Meat, Dairy, Legume, Fish & Seafood, Spice & Herb, Oil & Fat, Other)
- Per-month seasonality status: Out of season / Early / In season / Late season, with colour-coded badges
- Shop links per ingredient (URL + optional label per shop)
- See which recipes use each ingredient from the ingredient detail page

### Shops & aisles
- Create shops with named aisles
- Define multiple **locations** per shop (e.g. different branches)
- Set aisle ordering per location
- Map ingredient categories to aisles per location — used to sort grocery lists automatically
- Copy category→aisle mappings from one location to another

### Grocery list
- Select any combination of recipes and generate a consolidated ingredient list (quantities summed across recipes)
- Optionally sort by shop location: ingredients are grouped by aisle in the order you walk the shop
- Save a list for later (stored as a `SavedGroceryList`)
- Tick items off while shopping with a live progress bar
- Recipe summary sidebar: see which recipes contributed to the list and their main ingredients
- Per-ingredient recipe chips: see which recipe each item comes from, inline
- Archive completed lists; delete lists you no longer need

### Find Recipes
- Four-column selector (one per meal type)
- Per-section filters: must-include ingredients (boosts score), exclude ingredients (hides recipe), tags, max prep time, max cook time
- Results ranked by score — recipes matching no filter are shown in grey
- Select recipes across sections, choose a shop location, and generate a grocery list in-page
- Save directly to saved lists without leaving the page

### User accounts
- Register with a username (lowercase a–z only) and password
- Login / logout
- Every view requires authentication — no endpoint is publicly accessible
- Dark mode toggle (persisted in `localStorage`)

### Ownership & sharing
- Every recipe, ingredient, shop (and its aisles/locations), and grocery list is owned by the user who created it
- Data is private by default — other users cannot see or access your objects
- Share any recipe, ingredient, shop, or grocery list with specific users by username
- Shared users get read + write access; only the owner can manage the shared-with list
- Unowned objects (e.g. seeded base data) are visible to all users

---

## Prerequisites

- Python 3.12+
- pip

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/Nephty/nyochi.git
cd nyochi

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install django

# 4. Create the database directory and apply migrations
mkdir -p db
python manage.py migrate

# 5. Create your first user
python manage.py createsuperuser
# or register via the web UI after starting the server
```

---

## Running

```bash
python manage.py runserver
```

Visit [http://127.0.0.1:8000](http://127.0.0.1:8000). You will be redirected to the login page if not authenticated.

---

## Configuration

Settings are in `config/settings.py` and can be overridden with environment variables:

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Set to a long random string in production |
| `DJANGO_DEBUG` | `true` | Set to `false` in production |
| `ALLOWED_HOSTS` | `*` (when DEBUG) | Comma-separated list of allowed hostnames |

Example for production:

```bash
export DJANGO_SECRET_KEY="your-long-random-secret"
export DJANGO_DEBUG="false"
export ALLOWED_HOSTS="yourdomain.com"
python manage.py runserver
```

---

## Project structure

```
nyochi/
├── accounts/          # Auth app: register, login, logout
├── config/            # Django project settings and root URL conf
├── find_recipes/      # Recipe selector with scoring and grocery preview
├── grocery/           # Grocery list generation and saved list management
├── ingredients/       # Ingredient catalogue and seasonality
├── recipes/           # Core models, recipe CRUD, shared utils
│   ├── models.py      # All 14 models (Recipe, Ingredient, Shop, …)
│   ├── utils.py       # accessible_qs(), _save_grocery_list(), …
│   └── templatetags/  # recipe_extras: season badges, difficulty stars
├── shops/             # Shop, aisle, and location management
├── tags/              # Tag CRUD
├── templates/         # All HTML templates (one directory, per-app subdirs)
│   └── partials/      # HTMX partial templates
└── db/                # SQLite database (git-ignored)
```

---

## Data model (summary)

```
User (Django built-in)
├── Recipe              — owner FK, shared_with M2M
│   └── RecipeIngredient — per-recipe ingredient with quantity, unit, is_main
├── Ingredient          — owner FK, shared_with M2M, category, seasonality
│   ├── SeasonalAvailability — status per month (12 rows per ingredient)
│   └── ShopLink        — URL per shop for buying this ingredient
├── Shop                — owner FK, shared_with M2M
│   ├── Aisle           — named aisle within a shop
│   ├── ShopLocation    — named branch of a shop
│   ├── AisleOrder      — ordering of aisles within a location
│   └── CategoryAisleMapping — maps ingredient category → aisle for a location
├── SavedGroceryList    — owner FK, shared_with M2M, links to recipes
│   └── SavedGroceryItem — ingredient + quantity + in_cart flag
├── Tag                 — global, not owned
└── Unit                — global, not owned
```

All owned models follow the same access pattern: objects are visible when `owner IS NULL OR owner = user OR user IN shared_with`.

---

## Seeding sample data

A management command is not included, but you can seed via the Django shell:

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from recipes.models import Ingredient, Recipe, Unit, RecipeIngredient, IngredientCategory

User = get_user_model()
user = User.objects.get(username='yourname')

# Assign all unowned objects to yourself
from recipes.models import Ingredient, Recipe, RecipeIngredient, SavedGroceryList, SavedGroceryItem
for model in [Ingredient, Recipe, RecipeIngredient, SavedGroceryList, SavedGroceryItem]:
    model.objects.filter(owner=None).update(owner=user)
```
