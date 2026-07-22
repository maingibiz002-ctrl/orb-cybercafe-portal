import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from datetime import datetime
import base64

class MpesaClient:
    def __init__(self):
        # 1. READ YOUR REAL TILL OR FALLBACK TO SANDBOX TEST TILL (174379)
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', 'your_sandbox_consumer_key')
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', 'your_sandbox_consumer_secret')
        
        # This will hold your 6-digit Buy Goods Till number
        self.business_short_code = getattr(settings, 'MPESA_SHORTCODE', '174379') 
        self.passkey = getattr(settings, 'MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
        
    def get_access_token(self):
        """Fetches the OAuth token required to authenticate with Safaricom."""
        # FOR SANDBOX TESTING:
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        # FOR LIVE TILL: Uncomment the line below and comment the sandbox line
        # url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        
        try:
            response = requests.get(url, auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret))
            return response.json().get('access_token')
        except Exception as e:
            print(f"Error generating token: {e}")
            return None

    def send_stk_push(self, phone_number, amount, callback_url):
        """Triggers the STK Push on the user's phone."""
        token = self.get_access_token()
        if not token:
            return {"error": "Could not authenticate with Safaricom"}

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_str = f"{self.business_short_code}{self.passkey}{timestamp}"
        password = base64.b64encode(password_str.encode('utf-8')).decode('utf-8')

        headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure phone number is formatted as 2547XXXXXXXX or 2541XXXXXXXX
        formatted_phone = f"254{phone_number[-9:]}"

        payload = {
            # Your Till Number is used here as the initiator
            "BusinessShortCode": self.business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            
            # 2. CRUCIAL FOR BUY GOODS TILL: Change this from CustomerPayBillOnline
            "TransactionType": "CustomerBuyGoodsOnline",
            
            "Amount": int(amount),
            "PartyA": formatted_phone,
            
            # 3. CRUCIAL FOR BUY GOODS TILL: PartyB MUST be your 6-digit Till Number
            "PartyB": self.business_short_code,
            
            "PhoneNumber": formatted_phone,
            "CallBackURL": callback_url,
            "AccountReference": "OrbCyberCafe",
            "TransactionDesc": "WiFi Access Payment"
        }
          # Inside mpesa.py -> send_stk_push method
        payload = {
                  "BusinessShortCode": "174379",  # Your sandbox shortcode
                  "Password": password,
                  "Timestamp": timestamp,
                  "TransactionType": "CustomerPayBillOnline",  # ◄ CHOOSE THIS EXACTLY (Case-Sensitive)
                 # OR "TransactionType": "CustomerBuyGoodsOnline", if testing a Till shortcode
                 "Amount": amount,
                  "PartyA": phone_number,
                 "PartyB": "174379",
                 "PhoneNumber": phone_number,
                 "CallBackURL": callback_url,
                  "AccountReference": "orbcybercafe",
                 "TransactionDesc": "WiFi Payment"
        }

        # FOR SANDBOX TESTING:
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        # FOR LIVE PRODUCTION TILL: Uncomment the line below and comment the sandbox line
        # url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

        try:
            response = requests.post(url, json=payload, headers=headers)
            return response.json()
        except Exception as e:
            return {"error": str(e)}