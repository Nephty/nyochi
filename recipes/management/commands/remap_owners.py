"""Re-point ownership at the accounts the apps now share.

Before the shared login, Nyochi's rows were owned by hub user ids (and shared with them). The accounts database is new, so
those numbers mean nothing there. Run once, after the accounts exist:

    manage.py remap_owners --map 1=nephty --map 2=nephty --dry-run
    manage.py remap_owners --map 1=nephty --map 2=nephty

Every `owner` and every `shared_with` link of every model is rewritten in ONE statement per table (so 1->2 and 2->1 in the
same run cannot chain). Ids not in the map are left alone and listed.
"""
from collections import Counter

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When


class Command(BaseCommand):
    help = "Rewrite owner / shared_with user ids to the shared accounts (--map OLD_ID=username, repeatable)."

    def add_arguments(self, parser):
        parser.add_argument('--map', action='append', default=[], metavar='OLD_ID=USERNAME')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        mapping = {}
        for item in options['map']:
            old, _, username = item.partition('=')
            try:
                old_id = int(old)
            except ValueError:
                raise CommandError(f'Bad mapping {item!r}: expected OLD_ID=username')
            user = User.objects.using('accounts').filter(username__iexact=username.strip()).first()
            if user is None:
                raise CommandError(f'There is no account called {username!r} in the shared accounts database.')
            mapping[old_id] = user.pk
        if not mapping:
            raise CommandError('Give at least one --map OLD_ID=username.')
        whens = [When(owner_id=old, then=Value(new)) for old, new in mapping.items()]
        self.stdout.write('Mapping: ' + ', '.join(f'{o} -> {n}' for o, n in mapping.items()))
        leftovers = Counter()
        with transaction.atomic(using='default'):
            for model in apps.get_models():
                if model._meta.app_label != 'recipes':
                    continue
                if any(f.name == 'owner' for f in model._meta.get_fields()):
                    for owner in model.objects.exclude(owner_id=None).values_list('owner_id', flat=True).distinct():
                        if owner not in mapping:
                            leftovers[(model.__name__, owner)] += 1
                    n = model.objects.filter(owner_id__in=mapping).update(
                        owner_id=Case(*whens, output_field=IntegerField()))
                    if n:
                        self.stdout.write(f'  {model.__name__}.owner: {n} row(s)')
                if any(f.name == 'shared_with' for f in model._meta.get_fields()):
                    through = model.shared_with.through
                    src = f'{model._meta.model_name}_id'
                    seen = set()
                    for row in list(through.objects.all()):
                        new = mapping.get(row.user_id)
                        if new is None:
                            leftovers[(model.__name__ + '.shared_with', row.user_id)] += 1
                            seen.add((getattr(row, src), row.user_id))
                            continue
                        key = (getattr(row, src), new)
                        if key in seen:
                            row.delete()
                        else:
                            seen.add(key)
                            if new != row.user_id:
                                row.user_id = new
                                row.save(update_fields=['user'])
                                self.stdout.write(f'  {model.__name__}.shared_with: {row.user_id}')
            if options['dry_run']:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('Dry run: nothing was changed.'))
        for (where, old), n in sorted(leftovers.items()):
            self.stdout.write(self.style.WARNING(f'Not in the map: {where} owner/user {old} ({n}x)'))
