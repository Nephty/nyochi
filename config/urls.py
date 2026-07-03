from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('recipes.urls')),
    path('', include('ingredients.urls')),
    path('', include('shops.urls')),
    path('', include('tags.urls')),
    path('', include('grocery.urls')),
    path('', include('find_recipes.urls')),
]
