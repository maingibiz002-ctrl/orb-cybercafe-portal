import json
import os
import requests
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import Package

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_your_secret_key_here")

def guest_portal_view(request):
    """Fetches active packages from database and renders portal."""
    packages = Package.objects.filter(is_active=True).order_by('price')
    return render(request, 'guest_portal.html', {'packages': packages})


def initiate_payment(request):
    """Handles Paystack checkout initialization."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = data.get('amount')
            phone = data.get('phone')
            package_name = data.get('package')
            email = f"guest_{phone}@orbcybercafe.com"

            amount_in_cents = int(float(amount) * 100)

            headers = {
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "email": email,
                "amount": amount_in_cents,
                "currency": "KES",
                "metadata": {
                    "phone_number": phone,
                    "package": package_name
                }
            }

            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                headers=headers,
                json=payload,
                timeout=20
            )
            res_data = response.json()

            if res_data.get("status"):
                return JsonResponse({
                    "status": True,
                    "authorization_url": res_data["data"]["authorization_url"]
                })
            return JsonResponse({"status": False, "message": res_data.get("message", "Initialization failed")})

        except Exception as e:
            return JsonResponse({"status": False, "message": str(e)}, status=500)

    return JsonResponse({"status": False, "message": "Invalid request method"}, status=400)

def paystack_callback(request):
    """Handles payment completion redirects."""
    return render(request, 'guest_portal.html')

@csrf_exempt
def paystack_webhook(request):
    """Receives automated payment confirmation webhooks from Paystack."""
    if request.method == 'POST':
        return HttpResponse(status=200)
    return HttpResponse(status=400)