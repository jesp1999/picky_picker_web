from django.urls import path
from django.views.generic import TemplateView

from pickform.views import auth_view, discord_redirect_view, form_view

DCV_FILENAME = '1C50148033C120998D2A58356A948C73.txt'

urlpatterns = [
    path('auth/', auth_view, name='form-view'),
    path('auth/discord/redirect/', discord_redirect_view, name='form-view'),
    path('form/', form_view, name='form-view'),
    path(f'.well-known/{DCV_FILENAME}/', TemplateView.as_view(template_name=f'well-known/{DCV_FILENAME}')),
]
