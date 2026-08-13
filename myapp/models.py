from django.db import models
from django.utils import timezone

# 1. THE PACKAGES (What you are selling, e.g., Ksh. 60 for 24 hours)


class Package(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. 1 hour, 24 hours, Weekly")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price in Ksh, e.g. 10.00")
    duration_description = models.CharField(
        max_length=255, 
        default="Valid for continuous high-speed browsing.",
        help_text="e.g. Valid for 1 Hour of continuous high-speed browsing."
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide package from portal")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} - Ksh. {self.price}"


# 2. THE TRANSACTIONS (Recording every Paystack attempt via your existing schema)
class Transaction(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),  # Updated to match Paystack's success callback state
        ('FAILED', 'Failed'),
    ]

    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True)
    
    # We reuse this field to store Paystack's unique checkout reference string
    mpesa_checkout_id = models.CharField(max_length=100, unique=True)
    
    # We can store the Paystack transaction ID or gateway response text here
    mpesa_receipt_code = models.CharField(max_length=100, blank=True, null=True) 
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    # Add these inside class Transaction(models.Model) in your models.py:
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    ip_address = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.phone_number} - {self.status} (Ksh. {self.amount})"


# 3. ACTIVE SESSIONS (Who is currently connected and when they expire)
class ActiveSession(models.Model):
    mac_address = models.CharField(max_length=17, unique=True) # The physical device ID: "00:11:22:33:44:55"
    ip_address = models.CharField(max_length=15) # "192.168.88.254"
    package = models.ForeignKey(Package, on_delete=models.CASCADE) # Links back to what they bought
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        # Checks if the user still has time left
        return self.is_active and timezone.now() < self.expires_at

    def __str__(self):
        return f"MAC: {self.mac_address} (Expires: {self.expires_at})"

