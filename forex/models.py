from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

# Create your models here.

class Account(models.Model):
    account_name = models.CharField(max_length=100)
    account_balance = models.DecimalField(max_digits=15, decimal_places=2)
    base_currency = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.account_name} ({self.base_currency})"

class ForexPosition(models.Model):
    POSITION_TYPES = [
        ('LONG', 'Long'),
        ('SHORT', 'Short'),
    ]

    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('PENDING', 'Pending'),
    ]

    symbol = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=15, decimal_places=2)
    entry_price = models.DecimalField(max_digits=15, decimal_places=5)
    current_price = models.DecimalField(max_digits=15, decimal_places=5, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    position_type = models.CharField(max_length=5, choices=POSITION_TYPES)
    trade_date = models.DateTimeField()
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='positions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} {self.position_type} {self.quantity} @ {self.entry_price}"

    def calculate_pnl(self):
        if not self.current_price:
            return Decimal('0')
        
        if self.position_type == 'LONG':
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - self.current_price) * self.quantity

class WebSocketConnection(models.Model):
    channel_name = models.CharField(max_length=255, unique=True)
    groups = models.JSONField(default=list)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['channel_name']),
        ]

    def __str__(self):
        return f"Connection {self.channel_name}"

    @classmethod
    def cleanup_stale_connections(cls, max_age_minutes=5):
        """Remove connections older than max_age_minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=max_age_minutes)
        stale_connections = cls.objects.filter(last_seen__lt=cutoff_time)
        count = stale_connections.count()
        stale_connections.delete()
        return count
