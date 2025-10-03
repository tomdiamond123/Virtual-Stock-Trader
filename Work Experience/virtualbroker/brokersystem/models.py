from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal

# Create your models here.
class CustomUser(AbstractUser):
    # remove username, make email the unique identifier
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=10000, validators=[MinValueValidator(Decimal('0.00'))])

    USERNAME_FIELD = "email"        # login with email
    REQUIRED_FIELDS = [""]            # no extra fields required

    def __str__(self):
        return self.email

class BalanceHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.user.username
    
    def save(self, *args, **kwargs):
        self.balance = self.user.balance
        super().save(*args, **kwargs)

class Stock(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, unique=True)
    
    def __str__(self):
        return self.name

class PriceHistory(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = ("stock", "timestamp")
        indexes = [
            models.Index(fields=["stock", "-timestamp"]),
        ]
        ordering = ["-timestamp"]
    
    def __str__(self):
        return f"{self.stock.symbol} @ {self.price} ({self.timestamp:%Y-%m-%d %H:%M})"


class Transaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    side = models.CharField(choices=[('buy', 'Buy'), ('sell', 'Sell')], max_length=4)
    executed_at = models.DateTimeField(auto_now_add=True)#auto add the time when the transaction is executed
    
    def __str__(self):
        return f"{self.user.get_full_name()} {self.quantity} {self.stock.symbol}" 

class Position(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)  # Average cost price
    current_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Current market price
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'stock')
    
    def __str__(self):
        return f"{self.user.get_full_name()} {self.quantity} {self.stock.symbol}"
        
