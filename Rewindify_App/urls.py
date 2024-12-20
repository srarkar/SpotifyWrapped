from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import TemplateView
from authorize import views  # Import views from your current module

urlpatterns = [
    path("admin/", admin.site.urls),
    path("authorize/", include("authorize.urls")),  # Keep the include for 'authorize' URLs
    path("authorize/", include("django.contrib.auth.urls")),  # Include default auth URLs if needed
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("user_profile/", views.callback, name="user_profile"),  # Add this line for the user_profile view
]
