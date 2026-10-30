from django import forms
from django.forms import inlineformset_factory

import json

from . import kitchen
from .access import readable
from .models import Ingredient, Recipe, RecipeIngredient, Tag


class StyledFormMixin:
    """Give every widget the design system's class (.input / .select / .textarea)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple, forms.CheckboxInput,
                                   forms.HiddenInput)):
                continue
            kind = ('select' if isinstance(widget, forms.Select) else
                    'textarea' if isinstance(widget, forms.Textarea) else 'input')
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {kind}".strip()


class UniqueNameMixin(StyledFormMixin):
    """Names are unique per community, ignoring case. The community isn't a form field, so the model's constraint
    isn't checked by ModelForm: do it here. `owner` is the user making the change (it carries the community)."""
    owner_label = 'one'

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        from .community import community_of

        cid = self.instance.community_id if self.instance.pk else (community_of(self.owner) if self.owner else None)
        clash = type(self.instance).objects.filter(community_id=cid, name__iexact=name)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f'Your community already has {self.owner_label} called "{name}".')
        return name


class RecipeForm(StyledFormMixin, forms.ModelForm):
    new_tags = forms.CharField(required=False, max_length=200, label='New tags',
                               help_text='Comma separated; they are created for you.')

    class Meta:
        model = Recipe
        fields = ['name', 'difficulty', 'meal_type', 'prep_time', 'cook_time', 'tags']
        widgets = {
            'tags': forms.CheckboxSelectMultiple(),
            'difficulty': forms.RadioSelect(),
            'meal_type': forms.RadioSelect(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['tags'].queryset = readable(Tag, user) if user else Tag.objects.all()
        self.fields['tags'].required = False
        self.fields['difficulty'].choices = Recipe.Difficulty.choices
        self.fields['meal_type'].choices = Recipe.MealType.choices
        for f in ('prep_time', 'cook_time'):
            self.fields[f].widget.attrs.update(min=0, inputmode='numeric')
        # steps, tools and kitchenware come from the editor (static/nyochi/steps.js) as JSON
        for name in ('steps', 'tools', 'kitchenware'):
            self.fields[f'{name}_json'] = forms.CharField(required=False, widget=forms.HiddenInput())
            if not self.is_bound:
                self.initial[f'{name}_json'] = json.dumps(getattr(self.instance, name) or [])

    def _json(self, name):
        try:
            return json.loads(self.cleaned_data.get(f'{name}_json') or '[]')
        except ValueError:
            raise forms.ValidationError('The steps could not be read: reload the page and try again.')

    def clean(self):
        data = super().clean()
        data['steps'] = kitchen.clean_steps(self._json('steps'))
        data['tools'] = kitchen.clean_tools(self._json('tools'))
        data['kitchenware'] = kitchen.clean_kitchenware(self._json('kitchenware'))
        return data

    def save(self, commit=True):
        for name in ('steps', 'tools', 'kitchenware'):
            setattr(self.instance, name, self.cleaned_data[name])
        return super().save(commit)

    def save_tags(self, recipe):
        names = []
        for raw in self.cleaned_data.get('new_tags', '').split(','):
            name = ' '.join(raw.split())[:50]
            if name and name.lower() not in [n.lower() for n in names]:
                names.append(name)
        chosen = list(self.cleaned_data.get('tags', []))
        for name in names:
            tag = readable(Tag, self.user).filter(name__iexact=name).first()
            if tag is None:
                tag = Tag.objects.create(name=name, owner=self.user)
            if tag not in chosen:
                chosen.append(tag)
        recipe.tags.set(chosen)


class RecipeIngredientForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity', 'unit', 'is_main']
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingredient'].empty_label = 'Choose an ingredient…'
        self.fields['unit'].empty_label = 'unit'
        self.fields['unit'].label_from_instance = lambda u: u.abbreviation
        if user is not None:
            # keep the row's current ingredient selectable even if it was unshared since
            qs = readable(Ingredient, user)
            self.fields['ingredient'].queryset = qs.order_by('name')


RecipeIngredientFormSet = inlineformset_factory(
    Recipe, RecipeIngredient, form=RecipeIngredientForm,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)
