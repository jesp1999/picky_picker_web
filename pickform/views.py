import os
from pathlib import Path
from urllib.parse import unquote

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import render
from dotenv import load_dotenv

from pickform.auth import decrypt

load_dotenv(Path(__file__).parent.parent / '.env')

ACTIVITIES_FOLDER = os.getenv('ACTIVITIES_FOLDER')


def get_params_from_query_string(query_string: str) -> dict[str, str]:
    return {s.split('=')[0]: s.split('=')[1] for s in query_string.split('&')}


def form_view(request: WSGIRequest):
    if request.method == 'GET':
        query_string = request.META['QUERY_STRING']
        params = get_params_from_query_string(query_string)
        token_hex = params.get('token')
        token = bytes.fromhex(token_hex)
        iv_hex = params.get('iv')
        iv = bytes.fromhex(iv_hex)
        user = decrypt(token, iv)
        if not user:
            return HttpResponse("Error: Invalid or expired token.", status=401)

        with open(f'{ACTIVITIES_FOLDER}/games.csv', 'r') as f:
            activities = [line.partition(',')[0].strip() for line in f.readlines()]
        if os.path.exists(f'{ACTIVITIES_FOLDER}/players/{user}.csv'):
            with open(f'{ACTIVITIES_FOLDER}/players/{user}.csv', 'r') as f:
                selected_activities = [line.strip() for line in f.readlines()]
        else:
            selected_activities = []
        return render(
            request, 'form_template.html', {
                'activities': activities,
                'selected_activities': selected_activities,
                'token': token_hex,
                'iv': iv_hex,
            }
        )
    elif request.method == 'POST':
        # Process form data and update files or interact with Discord bot
        token = bytes.fromhex(request.POST.get('token'))
        iv = bytes.fromhex(request.POST.get('iv'))
        user = decrypt(token, iv)
        if not user:
            return HttpResponse("Error: Invalid or expired token.", status=401)

        checked_boxes = request.POST.getlist('activities')
        with open(f'{ACTIVITIES_FOLDER}/players/{user}.csv', 'w+') as f:
            f.writelines([label.strip() + '\n' for label in sorted(checked_boxes)])
        return HttpResponse('Accepted', status=202)
