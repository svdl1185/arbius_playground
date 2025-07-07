from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('playground/', views.playground, name='playground'),
    path('api/verify-signature/', views.verify_signature, name='verify_signature'),
    path('api/check-auth-status/', views.check_auth_status, name='check_auth_status'),
    path('api/logout-wallet/', views.logout_wallet, name='logout_wallet'),
] 