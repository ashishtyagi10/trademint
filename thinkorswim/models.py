from django.db import models
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

class Counterparty(models.Model):
    COUNTERPARTY_TYPES = [
        ('BANK', 'Bank'),
        ('BROKER', 'Broker'),
        ('EXCHANGE', 'Exchange'),
        ('CLEARING_HOUSE', 'Clearing House'),
        ('INVESTMENT_FIRM', 'Investment Firm'),
        ('OTHER', 'Other')
    ]

    CREDIT_RATINGS = [
        ('AAA', 'AAA'),
        ('AA+', 'AA+'),
        ('AA', 'AA'),
        ('AA-', 'AA-'),
        ('A+', 'A+'),
        ('A', 'A'),
        ('A-', 'A-'),
        ('BBB+', 'BBB+'),
        ('BBB', 'BBB'),
        ('BBB-', 'BBB-'),
        ('NR', 'Not Rated')
    ]

    name = models.CharField(max_length=100, unique=True)
    counterparty_type = models.CharField(max_length=20, choices=COUNTERPARTY_TYPES)
    credit_rating = models.CharField(max_length=5, choices=CREDIT_RATINGS, default='NR')
    legal_entity_identifier = models.CharField(max_length=20, unique=True, null=True, blank=True)
    active = models.BooleanField(default=True)
    country = models.CharField(max_length=50)
    address = models.TextField()
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    risk_score = models.IntegerField(default=0)  # 0-100 scale
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Counterparties"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.counterparty_type})"

    def get_exposure(self):
        """Calculate total exposure across all positions"""
        return sum(position.market_value for position in self.equityposition_set.all())

class EquityPosition(models.Model):
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
    entry_price = models.DecimalField(max_digits=15, decimal_places=2)
    current_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    position_type = models.CharField(max_length=5, choices=POSITION_TYPES)
    trade_date = models.DateTimeField()
    company_name = models.CharField(max_length=100)
    counterparty = models.ForeignKey(Counterparty, on_delete=models.CASCADE, related_name='positions')
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

    @property
    def market_value(self):
        """Calculate current market value of position"""
        return Decimal(str(self.quantity)) * self.current_price

    @property
    def unrealized_pl(self):
        """Calculate unrealized P&L"""
        if self.position_type == 'LONG':
            return (self.current_price - self.entry_price) * Decimal(str(self.quantity))
        else:  # SHORT
            return (self.entry_price - self.current_price) * Decimal(str(self.quantity))

    @property
    def pl_percentage(self):
        """Calculate P&L as a percentage"""
        if self.entry_price == 0:
            return Decimal('0')
        return (self.unrealized_pl / (self.entry_price * Decimal(str(self.quantity)))) * 100

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
