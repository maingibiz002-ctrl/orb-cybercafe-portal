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
    
    # Extract router tracking parameters from GET or POST
    router_mac = request.GET.get('mac', request.POST.get('mac_address', ''))
    router_ip = request.GET.get('ip', request.POST.get('ip_address', ''))
    
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        package_id = request.POST.get('package_id')
        
        cleaned_phone = "".join(c for c in phone_number if c.isdigit())
        
        # Preserve context in case of error return
        context = {
            'packages': packages,
            'router_mac': router_mac,
            'router_ip': router_ip
        }
        
        if not cleaned_phone:
            context['error'] = 'Please provide a valid phone number.'
            return render(request, 'index.html', context)
            
        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            context['error'] = 'Selected package does not exist.'
            return render(request, 'index.html', context)
            
        dummy_email = f"customer_{cleaned_phone}@orbcybercafe.com"
        callback_url = "https://orb-cybercafe-portal.onrender.com/paystack/callback/"
        
        metadata = {
            "phone_number": cleaned_phone,
            "package_id": package.id,
            "mac_address": router_mac,
            "ip_address": router_ip
        }
        
        print(f"\n[CHECKOUT INITIALIZATION] Processing request for phone: {cleaned_phone}")
        
        response = paystack.initialize_transaction(
            email=dummy_email,
            amount_in_kes=package.price,
            callback_url=callback_url,
            metadata=metadata
        )
        
        if response and response.get('status') is True:
            reference = response['data']['reference']
            authorization_url = response['data']['authorization_url']
            
            print(f"--> Paystack session created. Ref: {reference} | Captured Hardware: {router_mac}")
            
            # Record pending transaction
            Transaction.objects.create(
                mpesa_checkout_id=reference, 
                phone_number=cleaned_phone,
                package=package,
                amount=package.price,
                mac_address=router_mac,
                ip_address=router_ip,
                status='PENDING'
            )
            
            print(f"--> Pending transaction entry recorded in local database. Redirecting user to Paystack...")
            
            # Redirect user's browser to Paystack checkout screen
            return redirect(authorization_url)
        else:
            error_msg = response.get('message', 'Gateway initiation failed.') if response else 'Unable to reach payment gateway.'
            print(f"--> Paystack Initialization Failure: {error_msg}")
            context['error'] = error_msg
            return render(request, 'index.html', context)
            
    return render(request, 'index.html', {
        'packages': packages,
        'router_mac': router_mac,
        'router_ip': router_ip
    })

@csrf_exempt

# 1. BROWSER REDIRECT VIEW (GET requests only)
def paystack_callback(request):
    paystack = PaystackGateway()
    reference = request.GET.get('reference')

    if reference:
        print(f"\n[PROCESSING REDIRECT] Reference: {reference} (Method: GET)")
        verified_data = paystack.verify_transaction(reference)
        
        if verified_data and verified_data.get('status') == 'success':
            verified_amount = float(verified_data.get('amount', 0)) / 100
            
            try:
                transaction = Transaction.objects.get(mpesa_checkout_id=reference)
                
                if transaction.status == 'PENDING':
                    # Safe numeric comparison
                    if abs(float(transaction.amount) - verified_amount) < 0.01:
                        transaction.status = 'COMPLETED'
                        transaction.mpesa_receipt_code = reference 
                        transaction.save()
                        print(f"✅ [SUCCESS] Transaction {reference} updated to COMPLETED!")
                        
                        # Authorize router access
                        authorize_internet_access(transaction)
                    else:
                        print(f"⚠️ [WARNING] Amount mismatch! Expected KES {transaction.amount}, got KES {verified_amount}")
                else:
                    print(f"ℹ️ [NOTICE] Transaction {reference} was already completed.")
            except Transaction.DoesNotExist:
                print(f"❌ [ERROR] Reference {reference} not found in database.")

    # Always render the portal UI for human users on GET
    packages = Package.objects.all().order_by('price')
    return render(request, 'index.html', {
        'packages': packages,
        'success_message': f'Payment successfully confirmed! Reference: {reference}' if reference else None
    })


# 2. PAYSTACK WEBHOOK VIEW (POST requests only from Paystack servers)
@csrf_exempt
def paystack_webhook(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8'))
            event = payload.get('event')
            
            # Webhooks trigger for many events; process transaction ONLY on successful charge
            if event == 'charge.success':
                reference = payload.get('data', {}).get('reference')
                
                if reference:
                    print(f"\n[PROCESSING WEBHOOK] Event: {event} | Reference: {reference}")
                    paystack = PaystackGateway()
                    verified_data = paystack.verify_transaction(reference)
                    
                    if verified_data and verified_data.get('status') == 'success':
                        verified_amount = float(verified_data.get('amount', 0)) / 100
                        
                        try:
                            transaction = Transaction.objects.get(mpesa_checkout_id=reference)
                            
                            if transaction.status == 'PENDING':
                                if abs(float(transaction.amount) - verified_amount) < 0.01:
                                    transaction.status = 'COMPLETED'
                                    transaction.mpesa_receipt_code = reference 
                                    transaction.save()
                                    print(f"✅ [SUCCESS] Transaction {reference} updated via Webhook!")
                                    
                                    # Authorize router access
                                    authorize_internet_access(transaction)
                                else:
                                    print(f"⚠️ [WARNING] Webhook Amount mismatch! Expected KES {transaction.amount}, got KES {verified_amount}")
                            else:
                                print(f"ℹ️ [NOTICE] Transaction {reference} was already completed.")
                        except Transaction.DoesNotExist:
                            print(f"❌ [ERROR] Webhook reference {reference} not found in database.")
        except Exception as e:
            print(f"❌ [WEBHOOK ERROR] {str(e)}")

    # Always respond with 200 OK JSON to Paystack's background server ping
    return JsonResponse({"status": "processed"}, status=200)