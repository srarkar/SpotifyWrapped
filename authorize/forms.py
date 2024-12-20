from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from .models import SpotifyWrap


class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for user registration. Inherits from Django's UserCreationForm
    and adds custom validation for email and form field customization.
    """
    username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), required=True)
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Confirm Password")

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        """
        Validates the email field to ensure the email is unique.
        Raises a ValidationError if the email already exists in the database.
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already taken.")
        return email

    def __init__(self, *args, **kwargs):
        """
        Customizes the form fields, removing help texts for username and password fields.
        """
        super().__init__(*args, **kwargs)
        # Remove help texts
        self.fields['username'].help_text = None
        self.fields['password1'].help_text = ''
        self.fields['password2'].help_text = ''


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    A custom form for changing the user's password. Inherits from Django's PasswordChangeForm.
    Adds placeholders to the password fields for better UX.
    """
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Old Password'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'}))


class SpotifyWrapForm(forms.ModelForm):
    """
    A form for handling SpotifyWrap model data, allowing users to input and modify
    their Spotify wrap data like top tracks, artists, and playlists.
    """
    class Meta:
        model = SpotifyWrap
        fields = ['top_tracks', 'top_artists', 'top_genres', 'total_minutes', 'playlists', 'music_description']


# class WrapUploadForm(forms.ModelForm):
#     """
#     A form for uploading SpotifyWrap data, similar to the SpotifyWrapForm.
#     This class is currently commented out.
#     """
#     class Meta:
#         model = SpotifyWrap
#         fields = ['top_tracks', 'top_artists', 'top_genres', 'total_minutes', 'playlists', 'music_description']
