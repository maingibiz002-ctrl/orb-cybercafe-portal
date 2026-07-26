import uuid
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Package, Transaction, ActiveSession
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib import messages


def home_view(request):
    """Renders the personal homepage with services."""
    return render(request, 'home.html')


def guest_portal_view(request):
    packages = Package.objects.all()
    router_mac = request.GET.get('mac', '')
    router_ip = request.GET.get('ip', '')

    if request.method == 'POST':
        print("\n================ PAYSTACK DEBUG START ================")
        print("POST Data Received:", request.POST)

        package_id = request.POST.get('package_id')
        email = request.POST.get('email', 'guest@orbcybercafe.com')
        phone_number = request.POST.get('phone_number', '').strip()
        mac_address = request.POST.get('mac_address') or router_mac
        ip_address = request.POST.get('ip_address') or router_ip

        try:
            package = Package.objects.get(id=package_id)
            print(f"Package Found: {package.name} | Price: {package.price}")

            # Format phone number to standard format
            if phone_number.startswith('0'):
                clean_phone = '254' + phone_number[1:]
            elif not phone_number.startswith('254'):
                clean_phone = '254' + phone_number
            else:
                clean_phone = phone_number

            # Paystack expects amount in KES kobo/cents (e.g., KES 10 = 1000)
            amount_in_cents = int(float(package.price) * 100)

            # Retrieve Paystack Secret Key from settings/environment
            paystack_secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_your_secret_key_here')
            print(f"Secret Key Loaded: {'YES' if paystack_secret_key and not paystack_secret_key.startswith('sk_test_your_secret') else 'NO (Default/Missing)'}")

            paystack_url = "https://api.paystack.co/transaction/initialize"
            headers = {
                "Authorization": f"Bearer {paystack_secret_key}",
                "Content-Type": "application/json"
            }
            
            callback_url = request.build_absolute_uri('/paystack/callback/')

            payload = {
                "email": email,
                "amount": amount_in_cents,
                "currency": "KES",
                "callback_url": callback_url,
                "metadata": {
                    "phone_number": clean_phone,
                    "mac_address": mac_address,
                    "ip_address": ip_address,
                    "package_id": package.id
                }
            }

            print("Sending Payload to Paystack:", payload)

            # Call Paystack API
            response = requests.post(paystack_url, json=payload, headers=headers)
            print(f"Paystack HTTP Status Code: {response.status_code}")

            res_data = response.json()
            print("Paystack API Full Response:", res_data)
            print("================ PAYSTACK DEBUG END ==================\n")

            if res_data.get('status') and 'data' in res_data and 'authorization_url' in res_data['data']:
                reference = res_data['data']['reference']
                
                # Create pending transaction record
                Transaction.objects.create(
                    phone_number=clean_phone,
                    amount=package.price,
                    package=package,
                    mpesa_checkout_id=reference,
                    mac_address=mac_address,
                    ip_address=ip_address,
                    status='PENDING'
                )
                
                print(f"Redirecting user to Paystack: {res_data['data']['authorization_url']}")
                return redirect(res_data['data']['authorization_url'])
            else:
                error_msg = res_data.get('message', 'Failed to initialize Paystack transaction.')
                messages.error(request, f"Paystack Error: {error_msg}")

        except Package.DoesNotExist:
            print("ERROR: Package.DoesNotExist for ID:", package_id)
            messages.error(request, "Selected package is invalid.")
        except Exception as e:
            print("EXCEPTION OCCURRED:", str(e))
            messages.error(request, f"Error initializing payment: {str(e)}")

    return render(request, 'guest_portal.html', {
        'packages': packages,
        'router_mac': router_mac,
        'router_ip': router_ip
    })


def solutions_view(request):
    """Placeholder view for Digital Solutions."""
    return render(request, 'home.html')


def courses_view(request):
    """Placeholder view for Tech Courses."""
    return render(request, 'home.html')


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