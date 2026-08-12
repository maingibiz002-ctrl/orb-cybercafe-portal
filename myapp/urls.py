# wifi_app/urls.py
from django.urls import path
from . import views
urlpatterns = [
    # Main Site Route (Directs root URL directly to Guest Portal)
    path('', views.guest_portal_view, name='guest_portal'),
    path('portal/', views.guest_portal_view, name='guest_portal_alias'),

    # Paystack Integration Routes
    path('initiate-payment/', views.initiate_payment, name='initiate_payment'),
    path('paystack/callback/', views.paystack_callback, name='paystack_callback'),
    path('paystack/webhook/', views.paystack_webhook, name='paystack_webhook'),
]