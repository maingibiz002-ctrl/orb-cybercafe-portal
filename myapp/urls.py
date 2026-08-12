# wifi_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Main Site Routes
   path('', views.home_view, name='home'),
   path('portal/', views.guest_portal_view, name='guest_portal'),
    # Paystack Integration Routes
    path('paystack/callback/', views.paystack_callback, name='paystack_callback'),
    path('paystack/webhook/', views.paystack_webhook, name='paystack_webhook'),
]