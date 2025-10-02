from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Stock, PriceHistory, Transaction, Position, BalanceHistory

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Broker fields", {"fields": ("balance",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "balance", "is_staff")

admin.site.register(Stock)
admin.site.register(PriceHistory)
admin.site.register(Transaction)
admin.site.register(Position)
admin.site.register(BalanceHistory)