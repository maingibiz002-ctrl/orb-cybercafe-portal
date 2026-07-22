from django.contrib import admin
# We import our custom tables from models.py
from .models import Package, Transaction, ActiveSession

# We register them so they appear in your browser dashboard
admin.site.register(Package)
admin.site.register(Transaction)
admin.site.register(ActiveSession)


class TransactionAdmin(admin.ModelAdmin):
    # This lists the columns clearly in the admin table view
    list_display = ('id', 'phone_number', 'amount', 'mpesa_checkout_id', 'mpesa_receipt_code', 'status', 'created_at')
    
    # This adds a quick filter sidebar on the right side to sort by status or date
    list_filter = ('status', 'created_at')
    
    # This adds a search bar at the top to look up transactions by phone or receipt code
    search_fields = ('phone_number', 'mpesa_checkout_id', 'mpesa_receipt_code')
    
    # Keeps the records ordered by the newest transaction first
    ordering = ('-created_at',)