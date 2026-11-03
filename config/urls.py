"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from users import group_views, views as user_views
from users.mail import BrevoPasswordResetForm

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="schedules:index", permanent=False)),
    path("schedules/", include("schedules.urls")),
    path("messages/", include("messaging.urls")),
    path("admin/", admin.site.urls),
    # Authentication URLs
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "password_change/",
        auth_views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            form_class=BrevoPasswordResetForm,
            email_template_name="registration/password_reset_email.txt",
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("groups/", group_views.group_roster, name="group_roster"),
    path("groups/select/", group_views.group_select, name="group_select"),
    path("groups/create/", group_views.group_create, name="group_create"),
    path("groups/add/", group_views.group_add, name="group_add"),
    path("groups/role/", group_views.group_role, name="group_role"),
    path("groups/remove/", group_views.group_remove, name="group_remove"),
    path("groups/delete/", group_views.group_delete, name="group_delete"),
    path("account/members/", user_views.member_list, name="members"),
    path("account/members/new/", user_views.member_create, name="member_create"),
    path(
        "account/members/<int:pk>/deactivate/",
        user_views.member_deactivate,
        name="member_deactivate",
    ),
]

if settings.DEBUG and not settings.TESTING:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
