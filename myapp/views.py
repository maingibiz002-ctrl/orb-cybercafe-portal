import uuid
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from .models import Package, Transaction, ActiveSession
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib import messages


# myapp/views.py
from django.shortcuts import render

def home_view(request):
    return render(request, 'guest_portal.html')

import json
import os
import requests
from django.http import JsonResponse
from django.shortcuts import render

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_your_secret_key_here")

def home_view(request):
    return render(request, 'guest_portal.html')

def initiate_payment(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = data.get('amount')
            phone = data.get('phone')
            package_name = data.get('package')
            email = f"guest_{phone}@orbcybercafe.com"

            # Convert KSh to cents (multiply by 100 for Paystack)
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
    """
    Handles the user redirect after completing payment on Paystack.
    """
    reference = request.GET.get('reference') or request.GET.get('trxref')

    if reference:
        try:
            # Look up transaction by checkout ID or reference
            transaction = Transaction.objects.filter(mpesa_checkout_id=reference).first()
            
            if transaction:
                transaction.status = 'COMPLETED'
                transaction.save()
                
                # Create an active Wi-Fi session if needed
                ActiveSession.objects.get_or_create(
                    mac_address=transaction.mac_address,
                    defaults={'ip_address': transaction.ip_address}
                )

                messages.success(request, f"Payment successfully confirmed! Reference: {reference}")
            else:
                messages.success(request, f"Payment processed successfully! Reference: {reference}")

        except Exception as e:
            messages.warning(request, f"Payment received, but session update failed: {str(e)}")
    else:
        messages.error(request, "Invalid payment callback reference.")

    return redirect('guest_portal')


@csrf_exempt
def paystack_webhook(request):
    """
    Handles background notifications (event triggers) sent from Paystack servers.
    """
    if request.method == 'POST':
        # TODO: Verify Paystack signature header and process payment status
        return JsonResponse({'status': 'success'}, status=200)
    return HttpResponse(status=400)

