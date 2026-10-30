# Nyochi — recipes, seasons and shopping lists

A personal cookbook that builds the shopping list for you, in the order you walk the shop, and knows what things cost
(through the **Shopping** app of the same suite). Django 6 (runs on 5.2 too), vanilla ES modules, plain CSS tokens.
Accounts and sessions are **shared with Shopping** (one login for both apps, not the hub): see "Accounts" below.

Live at `nyochi.nephty.top` (service `recipe-book`, port 8002, dev port 8002 under `dev.sh`).

## What it does

- **Recipes**: index cards with prep/cook time, difficulty, meal type, tags, ingredients (quantity + unit, a star for
  the *main* ones). Client-side search and filters; an estimated cost and "N on sale" from Shopping.
- **Steps and what you need** (`recipes/kitchen.py`, JSON on `Recipe`: `steps`, `tools`, `kitchenware`): steps in two
  phases, *Ingredient set-up* (getting the ingredients ready) then *Preparation*, each with an optional appliance and
  timer; manual tools (free text with suggestions) and kitchenware from a fixed list (oven, stove, fridge, freezer,
  microwave, grill, blender, kettle) with a setting ("200 °C, fan"). Edited in the recipe form (`static/nyochi/steps.js`,
  hidden `*_json` fields, cleaned server-side; ↑↓ past a phase's edge moves the step to the other phase, Ctrl+Enter adds
  the next step). The old free-text Method became preparation steps, one per line (migration 0018).
- **Cooking guide** (`/recipes/<id>/cook/`, `static/nyochi/cook.js`): get-ready page (ingredients to tick, kitchenware,
  tools), then one step at a time with the appliance and its setting, a timer (keeps running when you move on, beeps),
  previous / next summaries, a progress bar with a flag over every step that uses an appliance; ←/→ or swipe; the screen
  stays on; the position is remembered per recipe in the browser.
- **Ingredients**: a category (**Categories** page: each account edits its own list: add, rename, reorder, delete with a move target; the defaults are created on first use) and a **season ribbon** (12 months: out / early / in / late, painted with a brush),
  plus **products in Shopping** (see below).
- **Plan**: tick recipes (filters: text, meal, tags, must-include / leave-out ingredients, max times, in-season first,
  all in the browser), scale portions (×0.25 – ×20), pick a shop location, and the receipt on the right builds itself:
  amounts merged across recipes (500 g + 1 kg = 1.5 kg), sections in the shop's walking order, what to buy and what it
  costs. Save it as a list, copy it as text, print it.
- **Lists**: saved shopping lists with check-off, extra hand-typed items, archive / restore, a chosen location.
- **Shops**: shops → locations (branches) → aisles. The **layout editor** sets each location's walking route (drag or ↑↓),
  which aisle each ingredient category is in, and exceptions for single ingredients; copy a layout between locations.
- **Sharing** (recipes, ingredients, shops, lists): by username (accounts shared with Shopping); shared people can read and edit, only the owner
  deletes or re-shares.

## The link to Shopping

Shopping (`../shopping`) fetches the stores' products and promotions. Nyochi reads it through a small **read-only JSON
API with a bearer token** (`shopping/core/ext_api.py`, `/api/ext/search/` and `/api/ext/products/`):

- An ingredient has any number of `ShoppingLink`s (`store|code`, Shopping's product identity), one *preferred*. Each keeps
  a **snapshot** (name, pack size, price, promotion, deal and real-deal figures, store page URL) refreshed in one batch
  call when older than 6 h, on any page that shows it (`recipes/shopping.py`). Shopping down = the last snapshot is shown
  and the pages say so. The old free-text web links (`ShopLink`) are kept in the database but no longer shown.
- `recipes/pricing` logic: pack sizes ("500 g", "6 x 33 cl") are parsed to grams / millilitres / pieces. A recipe's cost is
  proportional (a quarter of a 1 kg pack = a quarter of its price); a list line counts **whole packs**, minus the saving
  of the current promotion on those packs. Amounts and packs that can't be compared (clove vs grams) count as one pack and
  are shown with "≈".
- Which product is bought: the shop's own store if it has one (`Shop.shopping_store`), else the preferred one, else the
  cheapest. The receipt also shows what each store would cost for the lines it covers.
- The browser never calls Shopping (CSP `connect-src 'self'`): search for the product picker goes through
  `/shopping/search/`.
- Config: `SHOPPING_API_URL` (default `https://shopping.nephty.top`) and `SHOPPING_API_TOKEN_FILE` (NixOS: the
  `shoppingApiTokenFile` option, delivered as a systemd credential, so the file can be root-only). No token = the link is
  off and the UI says so. The token file is shared with Shopping's `apiTokenFile`; create it once on the VPS with
  `install -d -m 700 /etc/nephty && head -c 32 /dev/urandom | base64 | tr -d '\n' > /etc/nephty/shopping-api-token && chmod 600 /etc/nephty/shopping-api-token`.

## Accounts and communities (Home's labauth)

The house apps share **one login on Home** (not the hub's): users, sessions and communities live in the lab-auth
database Home owns (`ACCOUNTS_DB_PATH`, alias `accounts`, routed by `config/routers.py`, `labauth` app synced from
`home/labauth`). `LOGIN_URL` is Home's; `/login/` here only redirects. Nyochi never migrates that database in production
(Home's `home-accounts` unit does; recipe-book requires it).

- **Everything belongs to a community** (`recipes/community.py`): every row with an owner has a `community_id`; the
  owner is only who made it. New rows take the request's community (a context variable set by
  `recipes.community.CommunityMiddleware`), a child row its parent's, else (tests, commands) the owner's first community.
  Names are unique per community. Rows without a community (seeded) are global: read by all, changed by superusers.
- **Who may do what** (`recipes/access.py`): members whose community gives `nyochi.view` read its rows (labauth's
  `AppAccessMiddleware` keeps the others out); `nyochi.recipes.edit` (recipes, tags), `nyochi.ingredients.edit`
  (ingredients, categories, Shopping links), `nyochi.shops.edit` (shops, locations, aisles, layouts) and
  `nyochi.lists.edit` (plan saving, saved lists) create, change and delete. Templates' `mine` = "may change it here".
- Categories are per community (the ten defaults seeded on first use).
- Per-row sharing (`shared_with`, the Share buttons) and `remap_owners` are gone: the community is what is shared.
  Migration 0017 put every existing row in the first community (Home's bootstrap).

## Layout of the code

| Path | What |
|---|---|
| `recipes/` | **All models** (`models.py`), `access.py` (who can read / write / delete what), `grocery.py` (merge, layout, receipt), `shopping.py` (API client, snapshots, pricing), `costing.py`, `seasons.py`, `templatetags/nyo.py` (icons, money, ribbon), the recipe views and sharing |
| `ingredients/`, `shops/`, `tags/`, `grocery/` (saved lists), `find_recipes/` (the Plan page and its receipt API) | views, forms, urls |
| `config/` | settings, `middleware.py` (login required; JSON 403 with a login link for `fetch`), `routers.py` (auth/sessions/contenttypes/admin → the shared accounts DB), `storage.py` (hashed static files), `context.py` (messages → toasts) |
| `static/nyochi/` | `nyochi.css` (tokens + components, the Shopping family), ES modules (`ui.js` helpers, `shell.js`, `plan.js`, `receipt.js`, `layout.js`, `ribbon.js`, `picker.js`, `combo.js`, `lists.js`, `filter.js`), self-hosted fonts |
| `templates/` | server-rendered pages; interactive parts get their data as `json_script` |

### Data notes

- `auth_user` is in the shared accounts database: every `owner` / `shared_with` is declared `db_constraint=False`, `shared_with` is
  only ever read through its M2M table (two queries, never a join), and the admin hides it.
- **Access**: top-level objects (Recipe, Ingredient, Shop, SavedGroceryList, Tag) have owner + shared_with; their children
  (recipe ingredients, locations, aisles, layout rows, list items, links) follow the parent. An ingredient / tag is also
  *readable* when a recipe or list you can read uses it. Rows with no owner: everyone reads, superusers change.
- **Categories** are a per-account list (`Category`: stable `key`, editable `name`, `position`). Ingredients and shop layouts store the *key*, so renaming never touches them; deleting moves the account's ingredients to a chosen category and drops that category's layout mappings. Lists, the ingredient page and the layout editor use the viewer's names and order (`recipes/categories.py`); a key the viewer doesn't have (a shared ingredient) shows prettified.
- Names are unique **per owner**, ignoring case (a `Lower(name), owner` constraint, also checked in the forms).
- `Unit.dimension` / `factor` (mass → g, volume → ml, count → piece) let amounts be added; other units (clove, bunch) are
  only added to themselves. Seeded by migration `0014`.
- Layout: `AisleOrder` (route per location), `CategoryAisleMapping` (category → aisle), `IngredientAisle` (exception).
  Sorting: exception → category → "Elsewhere"; aisles without a position come after the ordered ones.
- The current month (seasons) is taken in `Europe/Brussels`.

## Running it

```bash
# from the lab root: dev.sh starts every app, Nyochi on 8002 (it migrates the shared accounts DB first)
./dev.sh

# or alone, with a Python that has Django: tests (68), no server needed
python manage.py test recipes
```
Tests use two databases (this app's and the accounts DB: `HubTestCase` in `recipes/tests/base.py`) and need no network
(Shopping is mocked). `nix run .#manage -- <cmd>` is the packaged `manage.py`.

UI checks that need the browser: `?theme=dark|light` forces a theme. An auto-login middleware in a
scratch settings module (not in the repo) is the easiest way to look at pages.

## Deployment

Pushed to `Nephty/nyochi`, pinned as the `nyochi` input of `.nix`; deployed by rebuilding on the VPS (see `.nix/DEPLOY.md`).
`flake.nix` builds `collectstatic` (hashed files, imports rewritten) and its `installPhase` lists the directories to ship:
add a new top-level directory there.
