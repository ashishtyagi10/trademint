from django.urls import path

from . import views

app_name = 'thinkorswim'

urlpatterns = [
    path('', views.index, name='index'),
]