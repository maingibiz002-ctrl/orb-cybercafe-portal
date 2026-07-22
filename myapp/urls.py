
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.guest_portal, name='guest_portal'),
    path('paystack/callback/', views.paystack_callback, name='paystack_callback'),
]