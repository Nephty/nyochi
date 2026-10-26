from django.urls import path

from . import views

urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/<int:pk>/rename/', views.CategoryRenameView.as_view(), name='category-rename'),
    path('categories/<int:pk>/move/<str:direction>/', views.CategoryMoveView.as_view(), name='category-move'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
]
