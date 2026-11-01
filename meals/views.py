"""The meal calendar: week (and phone day list), month, the assistant, and the JSON endpoints their scripts use."""
import calendar
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from recipes.access import readable, writable
from recipes.community import can_edit
from recipes.http import ApiError, api, body, positive_int
from recipes.models import Recipe, Tag

from . import planning
from .models import Meal
from .planning import SLOT_ICONS, SLOT_LABELS, SLOT_MEALS, SLOTS, monday, parse_day

MULT_MIN, MULT_MAX = Decimal('0.25'), Decimal('20')
MAX_BULK = 200


def _slots():
    return [{'value': s, 'label': SLOT_LABELS[s], 'icon': SLOT_ICONS[s], 'meals': SLOT_MEALS[s]} for s in SLOTS]


def _urls():
    return {
        'save': reverse('meal-save'), 'bulk': reverse('meal-bulk'), 'shop': reverse('meal-shop'),
        'week': reverse('meals'), 'month': reverse('meals-month'), 'assistant': reverse('meals-assistant'),
        'meal': reverse('meal-action', args=[0, 'x']).replace('/0/x/', '/{id}/{action}/'),
        'recipe': reverse('recipe-detail', args=[0]).replace('/0/', '/{id}/'),
        'cook': reverse('recipe-cook', args=[0]).replace('/0/', '/{id}/'),
    }


def _days(start, n):
    today = timezone.localdate()
    return [{'iso': (start + timedelta(days=i)).isoformat(), 'today': start + timedelta(days=i) == today}
            for i in range(n)]


class WeekView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        start = monday(parse_day(request.GET.get('week'), today))
        end = start + timedelta(days=6)
        meals = planning.meals_between(request.user, start, end)
        recipes = planning.recipes_json(request.user)
        # the assistant fills what is left of this week, or the whole week shown
        a_start = today if start <= today <= end else start
        return render(request, 'meals/week.html', {
            'page': 'meals', 'start': start, 'end': end,
            'prev': (start - timedelta(days=7)).isoformat(), 'next': (start + timedelta(days=7)).isoformat(),
            'is_this_week': start == monday(today),
            # Month opens today's month when today is shown, else the month most of the week is in (its Thursday)
            'month': (today if start <= today <= end else start + timedelta(days=3)).strftime('%Y-%m'),
            'assistant_query': f'start={a_start.isoformat()}&days={(end - a_start).days + 1}',
            'boot': {
                'start': start.isoformat(), 'days': _days(start, 7), 'slots': _slots(),
                'meals': [planning.meal_json(m) for m in meals],
                'recipes': recipes, 'ingredients': planning.ingredient_names(recipes),
                'lists': planning.lists_covering(request.user, start, end),
                'canEdit': can_edit(request.user, Meal), 'today': today.isoformat(), 'urls': _urls(),
                # the day a phone shows first: the one asked for (from the month), else today
                'focus': parse_day(request.GET.get('week'), today).isoformat(),
            },
        })


class MonthView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        first = parse_day(f"{request.GET.get('m', '')}-01", today.replace(day=1)).replace(day=1)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        start, end = monday(first), monday(last) + timedelta(days=6)
        by_day = {}
        for m in planning.meals_between(request.user, start, end):
            by_day.setdefault(m.day, []).append(m)
        weeks = []
        d = start
        while d <= end:
            weeks.append({'monday': d, 'days': [
                {'date': d + timedelta(days=i), 'meals': by_day.get(d + timedelta(days=i), []),
                 'other': (d + timedelta(days=i)).month != first.month, 'today': d + timedelta(days=i) == today}
                for i in range(7)]})
            d += timedelta(days=7)
        prev = (first - timedelta(days=1)).replace(day=1)
        nxt = last + timedelta(days=1)
        month_meals = [m for day, ms in by_day.items() if first <= day <= last for m in ms]
        return render(request, 'meals/month.html', {
            'page': 'meals', 'first': first, 'weeks': weeks, 'slot_icons': SLOT_ICONS,
            'prev': prev.strftime('%Y-%m'), 'next': nxt.strftime('%Y-%m'), 'is_this_month': first == today.replace(day=1),
            'is_future': first > today,
            'planned': sum(1 for m in month_meals if m.kind != 'text'),
            'empty_days': sum(1 for i in range((last - first).days + 1) if first + timedelta(days=i) not in by_day),
            'weekdays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            # phones: under the compact calendar, only the days that have something
            'planned_days': [d for w in weeks for d in w['days'] if d['meals'] and not d['other']],
        })


class AssistantView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        start = parse_day(request.GET.get('start'), monday(today) + timedelta(days=7))
        try:
            n = max(1, min(int(request.GET.get('days', 7)), planning.MAX_RANGE))
        except ValueError:
            n = 7
        end = start + timedelta(days=n - 1)
        meals = planning.meals_between(request.user, start, end)
        return render(request, 'meals/assistant.html', {
            'page': 'meals',
            'boot': {
                'start': start.isoformat(), 'n': n, 'today': today.isoformat(), 'slots': _slots(),
                'meals': [planning.meal_json(m) for m in meals],
                'history': planning.history(request.user, start, end),
                'recipes': planning.recipes_json(request.user),
                'tags': [{'id': t.pk, 'name': t.name} for t in readable(Tag, request.user)],
                'canEdit': can_edit(request.user, Meal), 'urls': _urls(),
            },
        })


def shop(request):
    """The Plan screen for the meals of a range of days."""
    today = timezone.localdate()
    start = parse_day(request.GET.get('start'), today)
    end = parse_day(request.GET.get('end'), start + timedelta(days=6))
    if end < start:
        start, end = end, start
    end = min(end, start + timedelta(days=planning.MAX_RANGE - 1))
    return HttpResponseRedirect(planning.plan_url(request.user, start, end))


# --------------------------------------------------------------------------- JSON

def _need_edit(request):
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    if not can_edit(request.user, Meal):
        raise ApiError('Your community does not let you change the meal calendar.', 403)


def _day(raw):
    d = parse_day(raw)
    if d is None:
        raise ApiError('Invalid day.')
    return d


def _slot(raw):
    if raw not in SLOTS:
        raise ApiError('Invalid slot.')
    return raw


def _mult(raw):
    try:
        mult = Decimal(str(raw if raw not in (None, '') else 1))
    except InvalidOperation:
        raise ApiError('Invalid portions.')
    if not MULT_MIN <= mult <= MULT_MAX:
        raise ApiError('Portions can be scaled from ×0.25 to ×20.')
    return mult


def _text(raw, what='Name', limit=200):
    text = ' '.join(str(raw or '').split())
    if len(text) > limit:
        raise ApiError(f'{what} is too long ({limit} characters at most).')
    return text


def _recipe(user, raw):
    recipe = readable(Recipe, user).filter(pk=positive_int(raw, 'recipe')).first()
    if recipe is None:
        raise ApiError('Unknown recipe.', 404)
    return recipe


def _next_position(user, day, slot):
    last = readable(Meal, user).filter(day=day, slot=slot).order_by('-position').values_list('position', flat=True).first()
    return 0 if last is None else last + 1


def _fill(meal, user, data):
    """Set a meal from {recipe | text, mult, note}; the kind of a leftovers meal can't change."""
    if meal.leftover_of_id:
        meal.note = _text(data.get('note'), 'Note')
        return
    if data.get('recipe'):
        recipe = _recipe(user, data['recipe'])
        meal.recipe, meal.title, meal.mult = recipe, recipe.name, _mult(data.get('mult'))
    else:
        title = _text(data.get('text'))
        if not title:
            raise ApiError('Pick a recipe or write what you eat.')
        meal.recipe, meal.title, meal.mult = None, title, Decimal('1')
    meal.note = _text(data.get('note'), 'Note')


def _respond(user, *meals, status=200, gone=()):
    ids = {m.pk for m in meals}
    fresh = sorted(readable(Meal, user).filter(pk__in=ids).select_related('recipe', 'leftover_of')
                   .prefetch_related('leftovers'), key=planning.slot_order)
    return JsonResponse({'meals': [planning.meal_json(m) for m in fresh], 'deleted': list(gone)}, status=status)


@api
def save(request):
    """Create or change one meal: {id?, day, slot, recipe | text, mult, note, leftovers: {day, slot} | null}.
    `leftovers` (recipe meals) adds a leftovers meal there; an existing one is moved; null removes them."""
    _need_edit(request)
    data = body(request)
    with transaction.atomic():
        if data.get('id'):
            meal = writable(Meal, request.user).filter(pk=positive_int(data['id'])).first()
            if meal is None:
                raise ApiError('This meal is gone.', 404)
            day, slot = _day(data.get('day', meal.day.isoformat())), _slot(data.get('slot', meal.slot))
            if (day, slot) != (meal.day, meal.slot):
                meal.position = _next_position(request.user, day, slot)
            meal.day, meal.slot = day, slot
        else:
            day, slot = _day(data.get('day')), _slot(data.get('slot'))
            meal = Meal(day=day, slot=slot, owner=request.user, position=_next_position(request.user, day, slot))
        _fill(meal, request.user, data)
        meal.save()
        touched, gone = [meal], []
        if meal.kind == 'recipe' and 'leftovers' in data:
            spec = data.get('leftovers')
            existing = list(meal.leftovers.all())
            if spec:
                lday, lslot = _day(spec.get('day')), _slot(spec.get('slot'))
                if lday < meal.day:
                    raise ApiError('Leftovers come after the meal.')
                left = existing[0] if existing else Meal(leftover_of=meal, owner=request.user)
                if left.pk is None or (left.day, left.slot) != (lday, lslot):
                    left.position = _next_position(request.user, lday, lslot)
                left.day, left.slot, left.title = lday, lslot, meal.title
                left.save()
                touched.append(left)
                for extra in existing[1:]:
                    gone.append(extra.pk)
                    extra.delete()
            else:
                for extra in existing:
                    gone.append(extra.pk)
                    extra.delete()
        for left in meal.leftovers.all():
            if left.title != meal.title:
                left.title = meal.title
                left.save(update_fields=['title'])
    return _respond(request.user, *touched, gone=gone)


@api
def bulk(request):
    """The assistant's "Add to the calendar": {meals: [{day, slot, recipe | text, mult}]}."""
    _need_edit(request)
    items = body(request).get('meals')
    if not isinstance(items, list) or not items:
        raise ApiError('Nothing to add.')
    if len(items) > MAX_BULK:
        raise ApiError(f'At most {MAX_BULK} meals at once.')
    made = []
    with transaction.atomic():
        for item in items:
            if not isinstance(item, dict):
                raise ApiError('Invalid meal.')
            day, slot = _day(item.get('day')), _slot(item.get('slot'))
            meal = Meal(day=day, slot=slot, owner=request.user, position=_next_position(request.user, day, slot))
            _fill(meal, request.user, item)
            meal.save()
            made.append(meal)
    return _respond(request.user, *made, status=201)


@api
def action(request, pk, action):
    """move {day, slot} · delete · cooked {cooked: bool}."""
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    meal = writable(Meal, request.user).filter(pk=pk).first() if can_edit(request.user, Meal) else None
    if meal is None:
        if not readable(Meal, request.user).filter(pk=pk).exists():
            raise ApiError('This meal is gone.', 404)
        raise ApiError('Your community does not let you change the meal calendar.', 403)
    data = body(request)
    if action == 'move':
        day, slot = _day(data.get('day')), _slot(data.get('slot'))
        if (day, slot) != (meal.day, meal.slot):
            meal.day, meal.slot, meal.position = day, slot, _next_position(request.user, day, slot)
            meal.save(update_fields=['day', 'slot', 'position'])
        return _respond(request.user, meal)
    if action == 'delete':
        gone = [meal.pk] + [l.pk for l in meal.leftovers.all()]
        meal.delete()
        return JsonResponse({'deleted': gone})
    if action == 'cooked':
        meal.cooked_at = timezone.now() if data.get('cooked', True) else None
        meal.save(update_fields=['cooked_at'])
        return _respond(request.user, meal)
    raise ApiError('Unknown action.', 404)
