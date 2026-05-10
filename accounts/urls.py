from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('logout/', views.logout_view, name='logout'),
    path('login/', views.login_view, name='login'),
]