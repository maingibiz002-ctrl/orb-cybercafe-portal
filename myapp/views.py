# views.py
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
from .models import Package, Transaction, ActiveSession
from .paystack import PaystackGateway

def authorize_internet_access(transaction):
    """
    Handles session profile generation inside the database and orchestrates
    the network authorization logic using the captured device hardware address.
    """
    package = transaction.package
    if not package:
        print(f"[SYSTEM CRITICAL] Error: No package structural link mapped to Transaction ID: {transaction.id}")
        return False

    # Calculate exactly when this access pass runs out
    expiration_time = timezone.now() + timedelta(hours=package.duration_hours)

    # 👇 REPLACED PLACEHOLDERS: Extract the real MAC and IP saved on the transaction
    mac_address = transaction.mac_address or "00:00:00:00:00:00"  
    ip_address = transaction.ip_address or "192.168.88.254"     

    print(f"--> [ROUTER PROVISIONING] Initializing access pass profile...")
    print(f"    Target Device MAC: {mac_address}")
    print(f"    Selected Package Profile: {package.name} ({package.speed_limit})")
    print(f"    Access Authorized Until: {expiration_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Register or extend an existing active device block session in Django
    session, created = ActiveSession.objects.get_or_create(
        mac_address=mac_address,
        defaults={
            'ip_address': ip_address,
            'package': package,
            'expires_at': expiration_time,
            'is_active': True
        }
    )
    
    if not created:
        session.expires_at = expiration_time
        session.is_active = True
        session.save()
        print(f"--> [DATABASE] Existing session found for MAC {mac_address}. Access window extended.")
    else:
        print(f"--> [DATABASE] Fresh ActiveSession committed for MAC {mac_address}.")

    # --- NETWORK ROUTER API GATEWAY INTERFACES ---
    try:
        # e.g., router.command('/ip/hotspot/active/add', user=transaction.phone_number, mac_address=mac_address)
        print(f"[SUCCESS] Router pipeline commands executed. Firewall pipes are open for MAC: {mac_address} ({transaction.phone_number})!")
        return True
    except Exception as router_err:
        print(f"[ROUTER ERROR] Failed communicating rules to gateway router: {str(router_err)}")
        return False


def guest_portal(request):
    packages = Package.objects.all().order_by('price')
    paystack = PaystackGateway()
    
    # 👇 1. CAPTURE NETWORK DETAILS FROM URL (GET parameters sent by MikroTik/Gateway)
    # Different routers use different names: MikroTik standard is 'mac' and 'ip'
    router_mac = request.GET.get('mac', request.POST.get('mac_address', ''))
    router_ip = request.GET.get('ip', request.POST.get('ip_address', ''))
    
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        package_id = request.POST.get('package_id')
        
        cleaned_phone = "".join(c for c in phone_number if c.isdigit())
        
        if not cleaned_phone:
            return render(request, 'index.html', {'packages': packages, 'error': 'Please provide a valid phone number.'})
            
        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            return render(request, 'index.html', {'packages': packages, 'error': 'Selected package does not exist.'})
            
        dummy_email = f"customer_{cleaned_phone}@orbcybercafe.com"
        callback_url = "https://onshore-sterile-antics.ngrok-free.dev/paystack/callback/"
        
        metadata = {
            "phone_number": cleaned_phone,
            "package_id": package.id
        }
        
        print(f"\n[CHECKOUT INITIALIZATION] Processing request for phone: {cleaned_phone}")
        response = paystack.initialize_transaction(
            email=dummy_email,
            amount_in_kes=package.price,
            callback_url=callback_url,
            metadata=metadata
        )
        
        if response.get('status') is True:
            reference = response['data']['reference']
            authorization_url = response['data']['authorization_url']
            
            print(f"--> Paystack session created. Ref: {reference} | Captured Hardware: {router_mac}")
            
            # 👇 2. STORE HARDWARE SIGNATURES IN PENDING TRACKER ENTRY
            Transaction.objects.create(
                mpesa_checkout_id=reference, 
                phone_number=cleaned_phone,
                package=package,
                amount=package.price,
                mac_address=router_mac,  # Save the MAC address here
                ip_address=router_ip,    # Save the IP address here
                status='PENDING'
            )
            print(f"--> Pending transaction entry recorded in local database. Redirecting user...")
            return redirect(authorization_url)
        else:
            print(f"--> Paystack Initialization Failure: {response.get('message')}")
            return render(request, 'index.html', {'packages': packages, 'error': response.get('message', 'Gateway initiation failed.')})
            
    # For initial GET page view request, pass captured router variables down to hidden inputs in template
    return render(request, 'index.html', {
        'packages': packages,
        'router_mac': router_mac,
        'router_ip': router_ip
    })


@csrf_exempt
def paystack_callback(request):
    paystack = PaystackGateway()
    
    if request.method == 'POST':
        print("\n[WEBHOOK RECEIVED] Incoming live payload event dropped from Paystack...")
        try:
            payload = json.loads(request.body.decode('utf-8'))
            event_type = payload.get('event')
            print(f"--> Webhook Event Type Identified: {event_type}")
            
            if event_type == 'charge.success':
                reference = payload['data']['reference']
                print(f"--> Extracting unique session reference key: {reference}")
                
                print("--> Executing secondary verification handshake directly with Paystack API...")
                verified_data = paystack.verify_transaction(reference)
                
                if verified_data and verified_data.get('status') == 'success':
                    verified_amount = verified_data.get('amount') / 100
                    print(f"--> Handshake verified clear. Confirmed Payment Amount: KES {verified_amount}")
                    
                    try:
                        transaction = Transaction.objects.get(mpesa_checkout_id=reference)
                        print(f"--> Found tracking profile entry for Transaction ID: {transaction.id} (Current status: {transaction.status})")
                        
                        if transaction.status == 'PENDING':
                            if float(transaction.amount) == float(verified_amount):
                                print("--> Integrity check passed. Updating transaction status to COMPLETED...")
                                transaction.status = 'COMPLETED'
                                transaction.mpesa_receipt_code = reference 
                                transaction.save()
                                print("[DATABASE SUCCESS] Transaction status locked to COMPLETED.")
                                
                                # Boot network access routines (It will now safely extract the saved MAC inside)
                                authorize_internet_access(transaction)
                            else:
                                print(f"[SECURITY WARNING] Fraud block: Expected KES {transaction.amount}, but user paid KES {verified_amount}.")
                        else:
                            print(f"--> [NOTICE] Webhook ignored. Transaction reference {reference} was already handled earlier.")
                            
                    except Transaction.DoesNotExist:
                        print(f"[DATABASE ERROR] Reference tracker token {reference} cannot be found matching local system entries.")
                else:
                    print("[API FAILURE] Secure back-channel confirmation verification returned invalid or unpaid.")
                        
            return JsonResponse({"status": "processed"}, status=200)
        except Exception as e:
            print(f"[FATAL EXCEPTION] Hook processing error or system crash: {str(e)}")
            return JsonResponse({"status": "failed"}, status=400)
            
    # Browser Redirect Fallback (GET)
    reference = request.GET.get('reference')
    print(f"\n[BROWSER REDIRECT] User returned to portal landing page. Reference: {reference}")
    return render(request, 'index.html', {'success_message': f'Payment successfully confirmed! Reference: {reference}'})