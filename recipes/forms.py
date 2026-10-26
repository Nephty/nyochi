from django import forms
from django.forms import inlineformset_factory

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
    """Names are unique per owner, ignoring case. The owner isn't a form field, so the model's constraint
    isn't checked by ModelForm: do it here."""
    owner_label = 'one'

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        owner_id = self.instance.owner_id if self.instance.pk else getattr(self.owner, 'pk', None)
        clash = type(self.instance).objects.filter(owner_id=owner_id, name__iexact=name)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f'You already have {self.owner_label} called "{name}".')
        return name


class RecipeForm(StyledFormMixin, forms.ModelForm):
    new_tags = forms.CharField(required=False, max_length=200, label='New tags',
                               help_text='Comma separated; they are created for you.')

    class Meta:
        model = Recipe
        fields = ['name', 'difficulty', 'meal_type', 'description', 'prep_time', 'cook_time', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
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
