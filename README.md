# Nyochi — recipes, seasons and shopping lists

A personal cookbook that builds the shopping list for you, in the order you walk the shop, and knows what things cost
(through the **Shopping** app of the same suite). Django 6 (runs on 5.2 too), vanilla ES modules, plain CSS tokens.
Accounts, sessions and per-user access live in the hub (see the repo's `CLAUDE.md`); this app only reads them.

Live at `nyochi.nephty.top` (service `recipe-book`, port 8002, dev port 8002 under `dev.sh`).

## What it does

- **Recipes**: index cards with prep/cook time, difficulty, meal type, tags, ingredients (quantity + unit, a star for
  the *main* ones). Client-side search and filters; an estimated cost and "N on sale" from Shopping.
- **Ingredients**: a category and a **season ribbon** (12 months: out / early / in / late, painted with a brush),
  plus **products in Shopping** (see below).
- **Plan**: tick recipes (filters: text, meal, tags, must-include / leave-out ingredients, max times, in-season first,
  all in the browser), scale portions (×0.25 – ×20), pick a shop location, and the receipt on the right builds itself:
  amounts merged across recipes (500 g + 1 kg = 1.5 kg), sections in the shop's walking order, what to buy and what it
  costs. Save it as a list, copy it as text, print it.
- **Lists**: saved shopping lists with check-off, extra hand-typed items, archive / restore, a chosen location.
- **Shops**: shops → locations (branches) → aisles. The **layout editor** sets each location's walking route (drag or ↑↓),
  which aisle each ingredient category is in, and exceptions for single ingredients; copy a layout between locations.
- **Sharing** (recipes, ingredients, shops, lists): by hub username; shared people can read and edit, only the owner
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

## Layout of the code

| Path | What |
|---|---|
| `recipes/` | **All models** (`models.py`), `access.py` (who can read / write / delete what), `grocery.py` (merge, layout, receipt), `shopping.py` (API client, snapshots, pricing), `costing.py`, `seasons.py`, `templatetags/nyo.py` (icons, money, ribbon), the recipe views and sharing |
| `ingredients/`, `shops/`, `tags/`, `grocery/` (saved lists), `find_recipes/` (the Plan page and its receipt API) | views, forms, urls |
| `config/` | settings, `middleware.py` (hub access check; JSON 403 with a login link for `fetch`), `routers.py` (auth/sessions → hub DB), `storage.py` (hashed static files), `context.py` (messages → toasts) |
| `static/nyochi/` | `nyochi.css` (tokens + components, the Shopping family), ES modules (`ui.js` helpers, `shell.js`, `plan.js`, `receipt.js`, `layout.js`, `ribbon.js`, `picker.js`, `combo.js`, `lists.js`, `filter.js`), self-hosted fonts |
| `templates/` | server-rendered pages; interactive parts get their data as `json_script` |

### Data notes

- `auth_user` is in the hub's database: every `owner` / `shared_with` is declared `db_constraint=False`, `shared_with` is
  only ever read through its M2M table (two queries, never a join), and the admin hides it.
- **Access**: top-level objects (Recipe, Ingredient, Shop, SavedGroceryList, Tag) have owner + shared_with; their children
  (recipe ingredients, locations, aisles, layout rows, list items, links) follow the parent. An ingredient / tag is also
  *readable* when a recipe or list you can read uses it. Rows with no owner: everyone reads, superusers change.
- Names are unique **per owner**, ignoring case (a `Lower(name), owner` constraint, also checked in the forms).
- `Unit.dimension` / `factor` (mass → g, volume → ml, count → piece) let amounts be added; other units (clove, bunch) are
  only added to themselves. Seeded by migration `0014`.
- Layout: `AisleOrder` (route per location), `CategoryAisleMapping` (category → aisle), `IngredientAisle` (exception).
  Sorting: exception → category → "Elsewhere"; aisles without a position come after the ordered ones.
- The current month (seasons) is taken in `Europe/Brussels`.

## Running it

```bash
# from the lab root: dev.sh starts hub (8000) and every app, Nyochi on 8002
./dev.sh

# or alone, with a Python that has Django: tests (68), no server needed
python manage.py test recipes
```
Tests use two databases (this app's and a stand-in hub: `HubTestCase` in `recipes/tests/base.py`) and need no network
(Shopping is mocked). `nix run .#manage -- <cmd>` is the packaged `manage.py`.

UI checks that need the browser: `?theme=dark|light` forces a theme. Without the hub, an auto-login middleware in a
scratch settings module (not in the repo) is the easiest way to look at pages.

## Deployment

Pushed to `Nephty/nyochi`, pinned as the `nyochi` input of `.nix`; deployed by rebuilding on the VPS (see `.nix/DEPLOY.md`).
`flake.nix` builds `collectstatic` (hashed files, imports rewritten) and its `installPhase` lists the directories to ship:
add a new top-level directory there.
