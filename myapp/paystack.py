# paystack.py
import requests
from django.conf import settings

class PaystackGateway:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def initialize_transaction(self, email, amount_in_kes, callback_url, metadata=None):
        """
        Initializes a transaction session with Paystack.
        Converts KES amount directly to cents/kobo required by Paystack.
        """
        url = f"{self.base_url}/transaction/initialize"
        amount_in_cents = int(float(amount_in_kes) * 100)
        
        payload = {
            "email": email,
            "amount": amount_in_cents,
            "currency": "KES",
            "callback_url": callback_url,
            "metadata": metadata or {}
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            return response.json()
        except Exception as e:
            print(f"--> Paystack Initialization Network Error: {str(e)}")
            return {"status": False, "message": "Connection to payment gateway failed."}

    def verify_transaction(self, reference):
        """
        Queries Paystack secure servers directly to confirm a payment status.
        """
        url = f"{self.base_url}/transaction/verify/{reference}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response_data = response.json()
            if response_data.get('status') is True:
                return response_data.get('data')
            return None
        except Exception as e:
            print(f"--> Paystack Verification Network Error: {str(e)}")
            return None