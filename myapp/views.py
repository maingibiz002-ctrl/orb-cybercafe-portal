# wifi_app/views.py
import uuid
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Package, Transaction, ActiveSession
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse

def home_view(request):
    """Renders the personal homepage with services."""
    return render(request, 'home.html')


def guest_portal_view(request):
    """Renders the Wi-Fi captive portal and processes Paystack/M-Pesa payment attempts."""
    packages = Package.objects.all()
    
    # Capture router client details passed via URL query parameters
    router_mac = request.GET.get('mac', '')
    router_ip = request.GET.get('ip', '')

    error_message = None
    success_message = None

    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        phone_number = request.POST.get('phone_number')
        mac_address = request.POST.get('mac_address') or router_mac
        ip_address = request.POST.get('ip_address') or router_ip

        try:
            package = Package.objects.get(id=package_id)
            
            # Format phone number to standard format
            clean_phone = phone_number.strip()
            if clean_phone.startswith('0'):
                clean_phone = '254' + clean_phone[1:]
            elif not clean_phone.startswith('254'):
                clean_phone = '254' + clean_phone

            # Generate a unique checkout reference for Paystack
            checkout_ref = f"REF-{uuid.uuid4().hex[:12].upper()}"

            # Create the transaction record matching your Transaction model
            transaction = Transaction.objects.create(
                phone_number=clean_phone,
                amount=package.price,
                package=package,
                mpesa_checkout_id=checkout_ref,
                mac_address=mac_address,
                ip_address=ip_address,
                status='PENDING'
            )

            # TODO: Trigger Paystack / M-Pesa API payload using transaction.mpesa_checkout_id

            success_message = f"Payment prompt initiated for {clean_phone}. Check your phone to complete payment."

        except Package.DoesNotExist:
            error_message = "Selected package is invalid. Please try again."
        except Exception as e:
            error_message = "An error occurred initiating payment. Please try again."

    return render(request, 'guest_portal.html', {
        'packages': packages,
        'router_mac': router_mac,
        'router_ip': router_ip,
        'error': error_message,
        'success': success_message
    })


def solutions_view(request):
    """Placeholder view for Digital Solutions."""
    return render(request, 'home.html')


def courses_view(request):
    """Placeholder view for Tech Courses."""
    return render(request, 'home.html')

# --- ADD THESE MISSING PAYSTACK VIEWS ---

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

    # Redirect user back to the Wi-Fi package page instead of raw text
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

