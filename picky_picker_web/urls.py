from django.urls import path
from pickform.views import form_view

urlpatterns = [
    path('form/', form_view, name='form-view'),
]
