from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic

from django.http import HttpResponse
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from django.shortcuts import redirect, render
import requests
import json
import base64
from spotipy.oauth2 import SpotifyOAuth
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import SpotifyWrap  # Ensure this import is present

from .forms import CustomUserCreationForm, SpotifyWrapForm
#from .models import UserSpotifyProfile, Wrap
import logging
import base64
import json
import random
import string
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from .forms import CustomPasswordChangeForm

import openai


# Spotify API and app credentials
CLIENT_ID = settings.SPOTIFY_CLIENT_ID
CLIENT_SECRET = settings.SPOTIFY_CLIENT_SECRET
REDIRECT_URI = settings.SPOTIFY_REDIRECT_URI
STATE_KEY = 'spotify_auth_state'
openai.api_key = settings.OPENAI_API_KEY  # Make sure you set this in your settings.py

def create_music_profile_description(top_artists, genres):
    """
    Creates a music profile description based on the user's top artists and genres.

    Args:
        top_artists (dict): A dictionary containing a list of the user's top artists.
        genres (set): A set of genres that the user listens to.

    Returns:
        str: A formatted prompt that describes the personality, fashion, and behavior traits of someone
             who enjoys the given music preferences.
    """
    artist_names = [artist['name'] for artist in top_artists['items']]
    genre_names = list(genres)

    prompt = f"""
    Based on the following music preferences, describe the personality, fashion, and behavior traits of someone who listens to this kind of music:

    Top Artists: {', '.join(artist_names)}
    Top Genres: {', '.join(genre_names)}

    The person enjoys these musical styles. What are they like in terms of personality, fashion choices, and what might their hobbies or interests be? Write the prompt in second person
    """
    return prompt

def get_music_description(prompt):
    """
    Sends a prompt to the OpenAI API to generate a description based on the user's music preferences.

    Args:
        prompt (str): A formatted prompt that will be used to generate the description.

    Returns:
        str: The generated music description, formatted as a string.
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # or "gpt-4"
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )
    description = response.choices[0].message['content'].strip()
    return description

def generate_random_string(length=16):
    """
    Generates a random alphanumeric string of a specified length.

    Args:
        length (int, optional): The length of the random string. Defaults to 16.

    Returns:
        str: A randomly generated alphanumeric string.
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def loginn(request):
    """
    Initiates the Spotify authorization process by generating a random state string
    and redirecting the user to Spotify's authorization URL.

    This function creates a state parameter to prevent CSRF attacks, and constructs
    the Spotify authorization URL with required scopes.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponseRedirect: A redirect to the Spotify authorization URL.
    """
    state = generate_random_string()
    request.session[STATE_KEY] = state

    # Spotify authorization URL
    scope = 'user-read-private user-read-email user-top-read user-library-read'
    auth_url = f'https://accounts.spotify.com/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={state}&scope={scope}'

    return redirect(auth_url)

def callback(request):
    """
    Handles the callback from Spotify after the user authorizes the application.
    This function exchanges the authorization code for an access token,
    fetches the user's profile data, and generates a custom Spotify wrap.

    Args:
        request: The HTTP request object containing the authorization code and state.

    Returns:
        HttpResponse or HttpResponseRedirect: A response to the user, either an error message
        or a redirect to the 'logged_in' page with the Spotify wrap details.
    """
    code = request.GET.get('code')
    state = request.GET.get('state')

    if not code:
        return HttpResponse("No authorization code received", status=400)

    # Exchange the authorization code for an access token
    auth = (settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET)
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.SPOTIFY_REDIRECT_URI,
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    token_url = 'https://accounts.spotify.com/api/token'
    response = requests.post(token_url, data=data, headers=headers, auth=auth)

    if response.status_code != 200:
        return HttpResponse("Error fetching token", status=500)

    token_data = response.json()
    access_token = token_data.get('access_token')

    if not access_token:
        return HttpResponse("Failed to retrieve access token", status=500)

    # Save access token to session
    request.session['spotify_token'] = access_token

    # Fetch user profile data from Spotify
    user_profile_url = 'https://api.spotify.com/v1/me'
    user_profile_headers = {
        'Authorization': f'Bearer {access_token}',
    }
    user_profile_response = requests.get(user_profile_url, headers=user_profile_headers)

    if user_profile_response.status_code != 200:
        return HttpResponse("Error fetching user profile", status=500)

    user_profile = user_profile_response.json()

    # Extract the display name and profile picture URL
    display_name = user_profile.get('display_name', '')
    profile_picture = None
    if 'images' in user_profile and len(user_profile['images']) > 0:
        profile_picture = user_profile['images'][0].get('url', None)

    # Fetch playlists and top tracks
    sp = spotipy.Spotify(auth=access_token)
    playlists = sp.current_user_playlists()
    top_tracks = sp.current_user_top_tracks(limit=5)
    top_artists = sp.current_user_top_artists(limit=5)
    total_minutes = 0  # Variable to store total listening time in minutes

    genres = set()  # Using a set to avoid duplicates
    for artist in top_artists['items']:
        artist_info = sp.artist(artist['id'])  # Get detailed artist information
        genres.update(artist_info['genres'])

    music_description_prompt = create_music_profile_description(top_artists, genres)
    music_description = get_music_description(music_description_prompt)

    top_tracks_with_previews = []

    for track in top_tracks['items']:
        preview_url = track['preview_url']  # Spotify provides 30-second preview URL
        top_tracks_with_previews.append({
            'name': track['name'],
            'artists': [artist['name'] for artist in track['artists']],
            'album_image': track['album']['images'][0]['url'] if track['album']['images'] else None,
            'preview_url': preview_url
        })

    for track in top_tracks['items']:
        track_duration_ms = track['duration_ms']
        total_minutes += track_duration_ms / 60000

    top_artists_with_images = []
    for artist in top_artists['items']:
        artist_name = artist['name']
        artist_image = artist['images'][0]['url'] if artist['images'] else None
        top_artists_with_images.append({
            'name': artist_name,
            'image': artist_image
        })

    playlists_with_images = []
    for playlist in playlists['items']:
        playlist_name = playlist['name']
        playlist_image = playlist['images'][0]['url'] if playlist['images'] else None
        playlists_with_images.append({
            'name': playlist_name,
            'image': playlist_image
        })

    # Check if the form was submitted to save the data
    spotify_wrap = SpotifyWrap(
        user=request.user,
        top_tracks=top_tracks_with_previews,
        top_artists=top_artists_with_images,
        top_genres=list(genres),
        total_minutes=round(total_minutes, 2),
        playlists=playlists_with_images,
        music_description=music_description,

        display_name=display_name,  # Save display name
        profile_picture=profile_picture  # Save profile picture URL
    )
    spotify_wrap.save()

    messages.success(request, "Your Spotify wrap has been saved!")

    # Pass the list of top tracks with previews to the template
    return render(request, 'registration/logged_in.html', {
        'profile': user_profile,
        'playlists': playlists['items'],
        'top_tracks': top_tracks_with_previews,
        'top_artists': top_artists['items'],
        'genres': list(genres) if genres else None,
        'total_minutes': round(total_minutes, 2) if total_minutes else None,
        'music_description': music_description,  # Send the description generated by the LLM
    })
@csrf_exempt
def refresh_token(request):
    """
    Handles refreshing the Spotify access token using a provided refresh token.

    This view accepts a POST request with a refresh token, sends a request to Spotify's
    API to obtain a new access token, and returns the new tokens as JSON.

    Args:
        request: The HTTP POST request containing the refresh token.

    Returns:
        JsonResponse: A response with the new tokens if the request is successful,
        or an error message if the refresh fails.
    """
    refresh_token = request.POST.get('refresh_token')

    # Prepare token refresh request
    token_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': 'Basic ' + base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode('utf-8'),
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }

    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        tokens = response.json()
        return JsonResponse(tokens)
    else:
        return JsonResponse({'error': 'failed_to_refresh_token'}, status=400)


def get_spotify_playlists(request):
    """
    Fetches the current user's Spotify playlists and renders them in a template.

    This view checks if the user has a valid access token in the session. If the token
    is missing, it redirects the user to the Spotify login. Otherwise, it retrieves
    the playlists of the logged-in user using the Spotify API.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the 'show_playlists.html' template with
        the user's playlists if the token is valid, or redirects to the Spotify login page.
    """
    access_token = request.session.get('spotify_token')
    if not access_token:
        return redirect('spotify_login')  # Redirect to login if token is missing

    sp = spotipy.Spotify(auth=access_token)
    playlists = sp.current_user_playlists()

    return render(request, 'registration/show_playlists.html', {'playlists': playlists['items']})


def save_spotify_wrap(request):
    """
    Saves a Spotify wrap for the logged-in user.

    This view processes a POST request containing data about the user's Spotify wrap
    (top tracks, top artists, top genres, etc.) and saves this data in the database
    associated with the current user.

    Args:
        request: The HTTP POST request containing the Spotify wrap data.

    Returns:
        HttpResponse: A success message if the data is saved successfully, or a
        redirect to the home page if the request method is not POST.
    """
    if request.method == 'POST':
        # Assuming `request.user` is the logged-in user
        spotify_wrap = SpotifyWrap(
            user=request.user,
            top_tracks=request.POST.get('top_tracks', []),  # This should come from your form
            top_artists=request.POST.get('top_artists', []),  # This should come from your form
            top_genres=request.POST.get('top_genres', []),    # This should come from your form
            total_minutes=request.POST.get('total_minutes', 0), # Similarly, retrieve the data you want
            playlists=request.POST.get('playlists', [])
        )
        spotify_wrap.save()
        return HttpResponse('Spotify wrap saved successfully!')

    return redirect('home')


class SignUpView(generic.CreateView):
    """
    Handles the user sign-up process.

    This view displays a user registration form, and upon successful submission,
    redirects the user to the login page.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that either renders the sign-up form or redirects
        the user to the login page upon success.
    """
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"


def link_spotify_success(request):
    """
    Renders a success page after linking the user's Spotify account.

    This view is called when the user successfully links their Spotify account to
    the application, and it renders a success page.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the 'link_spotify_success.html' template.
    """
    return render(request, 'registration/link_spotify_success.html')
@login_required
def wrap_post(request):
    """
    Displays the first Spotify wrap for the logged-in user or a message if none exists.

    This view attempts to retrieve the first Spotify wrap uploaded by the user
    and renders it in a template. If no wrap is found, a message is displayed.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the 'wrap_post.html' template with
        the wrap data or a message indicating no wraps are available.
    """
    try:
        wrap = SpotifyWrap.objects.first()  # This gets the first wrap if it exists
        if wrap is None:
            # No wraps found, you can handle this gracefully
            return render(request, 'registration/wrap_post.html', {'message': 'No wraps found.'})
    except SpotifyWrap.DoesNotExist:
        # If you prefer, you can also handle the exception explicitly
        return render(request, 'registration/wrap_post.html', {'message': 'No wraps found.'})

    # If a wrap is found, render it as usual
    return render(request, 'registration/wrap_post.html', {'wrap': wrap})


@login_required
def delete(request):
    """
    Deletes the logged-in user's account.

    This view handles the deletion of a user's account upon a POST request. After
    deletion, the user is redirected to the home page with a success message.

    Args:
        request: The HTTP POST request object for account deletion.

    Returns:
        HttpResponse: A redirect to the home page with a success message after deletion.
    """
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, "Your account has been deleted successfully.")
        return redirect('home')  # Redirect to home page or login page after account deletion

    return render(request, 'registration/delete.html')


def password_change(request):
    """
    Allows the logged-in user to change their password.

    This view presents a password change form, processes the submission, and
    updates the user's password if the form is valid. Upon success, the user
    is redirected to the home page.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that either renders the password change form
        or redirects to the home page upon successful password change.
    """
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            # Update the session to keep the user logged in after password change
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('home')  # Redirect to a page after successful password change
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'registration/password_change.html', {'form': form})


@login_required
def past_wraps(request):
    """
    Displays all past Spotify wraps of the logged-in user.

    This view retrieves and displays all Spotify wraps uploaded by the user, ordered
    by the creation date in descending order.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the 'past_wraps.html' template
        with the list of past wraps.
    """
    wraps = SpotifyWrap.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "registration/past_wraps.html", {"wraps": wraps})


def wrap_detail(request, wrap_id):
    """
    Displays the details of a specific Spotify wrap by ID.

    This view fetches and displays the details of a particular Spotify wrap based
    on the provided wrap ID.

    Args:
        request: The HTTP request object.
        wrap_id: The ID of the Spotify wrap to fetch.

    Returns:
        HttpResponse: A response that renders the 'wrap_detail.html' template
        with the details of the specified wrap.
    """
    wrap = get_object_or_404(SpotifyWrap, id=wrap_id)  # Fetch a specific wrap by ID
    return render(request, 'registration/wrap_detail.html', {'wrap': wrap})


@login_required
def song_guessing_game(request):
    """
    A guessing game where the user guesses the correct Spotify song.

    This view allows the user to play a song guessing game where they are shown
    a random selection of their top tracks and asked to guess which one is correct.
    Feedback is provided after each guess.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the 'song_guessing_game.html' template
        with the game data and feedback.
    """
    access_token = request.session.get('spotify_token')
    if not access_token:
        messages.success(request, "You have not generated any wraps yet. Redirecting...")
        return redirect('loginn')

    sp = spotipy.Spotify(auth=access_token)
    top_tracks = sp.current_user_top_tracks(limit=10)
    if not top_tracks['items']:
        return render(request, 'registration/song_guessing_game.html')

    def prepare_game_data():
        correct_track = random.choice(top_tracks['items'])
        correct_track_data = {
            'track_name': correct_track['name'],
            'track_preview_url': correct_track['preview_url'],
            'track_artist': ", ".join([artist['name'] for artist in correct_track['artists']]),
            'track_album_image': correct_track['album']['images'][0]['url'] if correct_track['album']['images'] else None
        }
        options = [correct_track]
        while len(options) < 4:
            random_track = random.choice(top_tracks['items'])
            if random_track not in options:
                options.append(random_track)
        random.shuffle(options)
        options_data = [{
            'track_name': track['name'],
            'track_artist': ", ".join([artist['name'] for artist in track['artists']]),
            'track_album_image': track['album']['images'][0]['url'] if track['album']['images'] else None
        } for track in options]
        return correct_track_data, options_data

    if 'correct_track' not in request.session or request.method == 'GET':
        correct_track_data, options_data = prepare_game_data()
        request.session['correct_track'] = correct_track_data
        request.session['options'] = options_data

    correct_track_data = request.session['correct_track']
    options_data = request.session['options']
    feedback = None

    if request.method == 'POST':
        user_guess = request.POST.get('user_guess').strip()
        correct_answer = correct_track_data['track_name'].strip()
        if user_guess.lower() == correct_answer.lower():
            feedback = "Correct! You guessed the right song."
            correct_track_data, options_data = prepare_game_data()
            request.session['correct_track'] = correct_track_data
            request.session['options'] = options_data
        else:
            feedback = f"Incorrect! The correct answer was '{correct_answer}'."

    return render(request, 'registration/song_guessing_game.html', {
        **correct_track_data,
        'options': options_data,
        'feedback': feedback
    })
def contact(request):
    """
    Renders the contact page.

    This view simply renders a static contact page, where users can
    view contact information or a form to get in touch.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the 'contact.html' template.
    """
    return render(request, 'registration/contact.html')


@login_required
def delete_wrap(request, wrap_id):
    """
    Deletes a specific Spotify wrap for the logged-in user.

    This view allows users to delete a wrap by its ID, provided it belongs
    to the current user. After deletion, the user is redirected to their
    list of wraps.

    Args:
        request: The HTTP request object.
        wrap_id: The ID of the Spotify wrap to delete.

    Returns:
        HttpResponse: A redirect to the wraps list view after deletion.
    """
    wrap = get_object_or_404(SpotifyWrap, id=wrap_id, user=request.user)
    wrap.delete()
    return redirect('past_wraps')  # Replace with the name of your wraps list view


@login_required
def upload_wrap(request):
    """
    Handles uploading a new Spotify wrap.

    This view processes a form to upload a Spotify wrap. If the form is valid,
    it saves the wrap data and associates it with the logged-in user.
    The user is then redirected to view their uploaded wrap.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A response that renders the wrap upload form or redirects
        to the 'wrap_post' view upon successful submission.
    """
    if request.method == 'POST':
        form = WrapUploadForm(request.POST)
        if form.is_valid():
            # Save the wrap data in the database
            wrap = form.save(commit=False)
            wrap.user = request.user  # Associate the wrap with the current user
            wrap.save()
            return redirect('wrap_post')  # Redirect to the wrap post page to see the uploaded wrap
    else:
        form = SpotifyWrapForm()

    return render(request, 'registration/wrap_post.html', {'form': form})
