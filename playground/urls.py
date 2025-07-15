from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('playground/', views.playground, name='playground'),
    path('gallery/', views.gallery_index, name='gallery_index'),
    path('gallery/image/<int:image_id>/', views.image_detail, name='image_detail'),
    path('api/verify-signature/', views.verify_signature, name='verify_signature'),
    path('api/check-auth-status/', views.check_auth_status, name='check_auth_status'),
    path('api/logout-wallet/', views.logout_wallet, name='logout_wallet'),
    path('api/image/<int:image_id>/upvote/', views.toggle_upvote, name='toggle_upvote'),
    path('api/image/<int:image_id>/reaction/', views.toggle_reaction, name='toggle_reaction'),
    path('api/image/<int:image_id>/comment/', views.add_comment, name='add_comment'),
    path('api/gallery/images/', views.gallery_images_api, name='gallery_images_api'),
    
    # Stats Dashboard (replacing mining dashboard)
    path('dashboard/', views.stats_dashboard, name='stats_dashboard'),
] 