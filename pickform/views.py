import os
from base64 import b64decode
from pathlib import Path
from urllib.parse import unquote

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import render
from dotenv import load_dotenv

from pickform.auth import decrypt

load_dotenv(Path(__file__).parent.parent / '.env')

ACTIVITIES_FOLDER = os.getenv('ACTIVITIES_FOLDER')


def form_view(request: WSGIRequest):
    if request.method == 'GET':
        print(f'{request.GET=}')
        print(f'{request.GET.get("token")=}')
        print(f'{unquote(request.GET.get("token"))=}')
        print(f'{b64decode(unquote(request.GET.get("token")))=}')
        token = b64decode(unquote(request.GET.get('token')))
        iv = b64decode(unquote(request.GET.get('iv')))
        print(iv)
        user = decrypt(token, iv)
        if not user:
            return HttpResponse("Error: Invalid or expired token.", status=401)

        with open(f'{ACTIVITIES_FOLDER}/games.csv', 'r') as f:
            activities = [line.partition(',')[0] for line in f.readlines()]
        return render(
            request, 'form_template.html', {
                'activities': activities,
                'token': token,
                'iv': iv,
            }
        )
    elif request.method == 'POST':
        # Process form data and update files or interact with Discord bot
        token = unquote(request.POST.get('token'))
        iv = unquote(request.POST.get('iv'))
        user = decrypt(token, iv)
        if not user:
            return HttpResponse("Error: Invalid or expired token.", status=401)

        checked_boxes = request.POST.getlist('activities')
        with open(f'{ACTIVITIES_FOLDER}/players/{user}.csv', 'w+') as f:
            f.writelines([label.strip() + '\n' for label in sorted(checked_boxes)])
        return HttpResponse('Accepted', status=202)
