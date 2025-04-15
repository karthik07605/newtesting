from django.urls import path,include
from idea import views
from .views import *

urlpatterns = [
    # Your URL patterns
    path('create_lobby/', views.create_lobby, name='create_lobby'),
    path('join-lobby/', views.join_lobby, name='join_lobby'),
    path('lobby/host/<int:user_id>/<str:code>/', views.host_view, name='host_view'),
    path('lobby/participant/<int:user_id>/<str:code>/', views.participant_view, name='participant_view'),
    path('run-code/', views.run_code, name='run_code'),
    path('update-host-code/', views.update_host_code, name='update_host_code'),
    path('get-host-code/<str:code>/', views.get_host_code, name='get_host_code'),
    path('send-message/', views.send_message, name='send_message'),
    path('get-messages/<str:code>/', views.get_messages, name='get_messages'),
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path("accounts/",include('allauth.urls')),
    path("success/",login,name='success'),
    path('close-lobby/<str:code>/', views.close_lobby, name='close_lobby'),
    path('mainpage/',afterlogin, name='afterlogin'),
    path('logout/',logout,name='logout'),
]
