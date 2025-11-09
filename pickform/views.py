import os
from datetime import timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse

import requests
import base64
import hashlib
import secrets
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

ACTIVITIES_FOLDER = os.getenv('ACTIVITIES_FOLDER')
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
COOKIE_SECURE = os.getenv("DJANGO_SECURE_COOKIES", "1") == "1"
DISCORD_ME_URL = "https://discord.com/api/users/@me"
REDIRECT_URI = os.getenv("REDIRECT_URI")
TOKEN_URL = "https://discord.com/api/oauth2/token"


def _set_token_cookies(resp: HttpResponse, access_token: str, refresh_token: str, expires_in: int):
    # access token cookie lifetime = expires_in seconds
    resp.set_cookie(
        "access_token",
        access_token,
        max_age=int(expires_in),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Lax",
    )
    # refresh token typically longer-lived; example: 30 days
    resp.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=int(timedelta(days=30).total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Lax",
    )


def _get_discord_user(request: WSGIRequest) -> Optional[str]:
    """
    Fetch the Discord user for the `access_token` cookie and memoize it on
    `request._discord_user` for the lifetime of this request.
    Returns the user JSON dict on success or None on failure.
    """
    access_token = request.COOKIES.get("access_token")
    if not access_token:
        return None

    try:
        resp = requests.get(
            DISCORD_ME_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=5,
        )
    except requests.RequestException:
        return None

    if not resp.ok:
        return None

    try:
        user_json = resp.json()
    except ValueError:
        user_json = {}

    return user_json.get('username', '').lower() or None


@require_http_methods(["GET"])
def auth_view(request: WSGIRequest):
    """
    Redirect user to Discord authorize URL. Preserve original destination
    in the `state` parameter (URL-encoded).
    """
    # preserve the full path + query so we can return the user there after auth
    next_path = request.GET.get("next") or request.get_full_path()
    state = quote(next_path, safe="")

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()

    redirect_uri = quote(REDIRECT_URI, safe="")
    authorize_url = (
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}"
        f"&response_type=code&redirect_uri={redirect_uri}&scope=identify&state={state}"
        f"&code_challenge={code_challenge}&code_challenge_method=S256"
    )

    response = redirect(authorize_url)
    response.set_cookie(
        'pkce_verifier',
        code_verifier,
        max_age=60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite='Lax',
    )
    return response


@require_http_methods(["GET"])
def discord_redirect_view(request: WSGIRequest):
    code = request.GET.get("code")
    if not code:
        return HttpResponse("Missing code parameter in redirect from Discord", status=400)

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    code_verifier = request.COOKIES.get('pkce_verifier')
    if code_verifier:
        data["code_verifier"] = code_verifier

    resp = requests.post(
        TOKEN_URL,
        data=data,
        auth=(CLIENT_ID, CLIENT_SECRET),
        headers={"Accept": "application/json"},
        timeout=10,
    )

    if not resp.ok:
        return HttpResponse(f"Token exchange failed: {resp.status_code}", status=resp.status_code)

    token_data = resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        return HttpResponse("Token response missing fields", status=502)

    # Determine redirect target from state (if provided)
    state = request.GET.get("state")
    if state:
        redirect_target = unquote(state)
        parsed = urlparse(redirect_target)
        # prevent open-redirect: only allow internal paths (no netloc)
        if parsed.netloc:
            redirect_target = "/form"
    else:
        redirect_target = "/form"

    # Clear the PKCE cookie after use
    response = redirect(redirect_target)
    _set_token_cookies(response, access_token, refresh_token, expires_in)
    response.set_cookie('pkce_verifier', '', max_age=0)
    return response


def form_view(request: WSGIRequest):
    if request.method == 'GET':
        if not request.COOKIES.get("access_token"):
            next_path = quote(request.get_full_path(), safe="")
            return redirect(f"/auth?next={next_path}")

        discord_user = _get_discord_user(request)
        if not discord_user:
            return HttpResponse("Unauthorized: invalid or expired access token", status=401)

        with open(f'{ACTIVITIES_FOLDER}/games.csv', 'r') as f:
            activities = [line.partition(',')[0].strip() for line in f.readlines()]
        if os.path.exists(f'{ACTIVITIES_FOLDER}/players/{discord_user}.csv'):
            with open(f'{ACTIVITIES_FOLDER}/players/{discord_user}.csv', 'r') as f:
                selected_activities = [line.strip() for line in f.readlines()]
        else:
            selected_activities = []
        return render(
            request, 'form_template.html', {
                'activities': activities,
                'selected_activities': selected_activities,
            }
        )
    elif request.method == 'POST':
        discord_user = _get_discord_user(request)
        if not discord_user:
            return HttpResponse("Unauthorized: invalid or expired access token", status=401)

        checked_boxes = request.POST.getlist('activities')
        with open(f'{ACTIVITIES_FOLDER}/players/{discord_user}.csv', 'w+') as f:
            f.writelines([label.strip() + '\n' for label in sorted(checked_boxes)])
        return HttpResponse('Accepted', status=202)
