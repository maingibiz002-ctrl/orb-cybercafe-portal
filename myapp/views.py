import json
import os
import requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_your_secret_key_here")

# Static fallback packages while running without a database
PACKAGES = [
    {"id": 1, "name": "1 Hour Quick Surf", "duration": "1 Hour", "price": 50},
    {"id": 2, "name": "3 Hours Study Pass", "duration": "3 Hours", "price": 120},
    {"id": 3, "name": "Daily Unlimited", "duration": "24 Hours", "price": 250},
]


def guest_portal_view(request):
    """Renders the guest portal using static package options without database queries."""
    return render(request, "guest_portal.html", {"packages": PACKAGES})


def initiate_payment(request):
    """Handles Paystack checkout initialization."""
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body or "{}")
        amount = data.get("amount")
        phone = str(data.get("phone", "")).strip()
        package_name = str(data.get("package", "Internet Package")).strip()

        if amount is None or float(amount) <= 0:
            return JsonResponse({"status": False, "message": "Valid amount is required"}, status=400)

        if not phone:
            return JsonResponse({"status": False, "message": "Phone number is required"}, status=400)

        safe_phone = "".join(ch for ch in phone if ch.isalnum()) or "guest"
        email = f"guest_{safe_phone}@orbcybercafe.com"
        amount_in_subunits = round(float(amount) * 100)

        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "email": email,
            "amount": amount_in_subunits,
            "currency": "KES",
            "metadata": {
                "phone_number": phone,
                "package": package_name,
            },
        }

        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers,
            json=payload,
            timeout=20,
        )
        res_data = response.json()

        if response.ok and res_data.get("status"):
            return JsonResponse({
                "status": True,
                "authorization_url": res_data["data"]["authorization_url"],
            })

        return JsonResponse(
            {"status": False, "message": res_data.get("message", "Initialization failed")},
            status=400,
        )

    except ValueError:
        return JsonResponse({"status": False, "message": "Invalid amount format"}, status=400)
    except requests.RequestException as e:
        return JsonResponse({"status": False, "message": f"Payment gateway error: {e}"}, status=502)
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)


def paystack_callback(request):
    """Verifies Paystack payment reference and renders portal with payment status."""
    reference = request.GET.get("reference", "")
    payment_successful = False

    if reference and PAYSTACK_SECRET_KEY != "sk_test_your_secret_key_here":
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        }
        try:
            res = requests.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=headers,
                timeout=15,
            )
            res_data = res.json()
            if res.ok and res_data.get("status") and res_data.get("data", {}).get("status") == "success":
                payment_successful = True
        except Exception:
            payment_successful = False

    return render(
        request,
        "guest_portal.html",
        {
            "packages": PACKAGES,
            "payment_success": payment_successful,
            "reference": reference,
        },
    )


@csrf_exempt
def paystack_webhook(request):
    """Receives automated payment confirmation webhooks from Paystack."""
    if request.method == "POST":
        return HttpResponse(status=200)
    return HttpResponse(status=400)