from django.urls import path
from . import views

urlpatterns = [
    path('tags/', views.TagListView.as_view(), name='tag-list'),
    path('tags/<int:pk>/delete/', views.TagDeleteView.as_view(), name='tag-delete'),
]
