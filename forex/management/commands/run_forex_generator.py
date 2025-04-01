from django.core.management.base import BaseCommand
from django.utils import timezone
from forex.models import Account, ForexPosition
from decimal import Decimal
import random
import time
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class Command(BaseCommand):
    help = 'Generates random Forex data'

    def __init__(self):
        super().__init__()
        self.currency_pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD']

    def handle(self, *args, **options):
        self.stdout.write('Starting Forex data generator...')
        self._ensure_initial_data()
        
        while True:
            try:
                self._update_random_position()
                time.sleep(5)  # Update every 5 seconds
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS('Generator stopped'))
                break

    def _ensure_initial_data(self):
        if Account.objects.count() == 0:
            self._create_initial_accounts()
        
        if ForexPosition.objects.count() == 0:
            self._create_initial_positions()

    def _create_initial_accounts(self):
        accounts = [
            ('Trading Account 1', 'USD', Decimal('1000000')),
            ('Trading Account 2', 'EUR', Decimal('850000')),
            ('Trading Account 3', 'GBP', Decimal('750000'))
        ]

        for name, currency, balance in accounts:
            Account.objects.create(
                account_name=name,
                base_currency=currency,
                account_balance=balance,
                is_active=True
            )
        self.stdout.write(self.style.SUCCESS('Created initial accounts'))

    def _create_initial_positions(self):
        accounts = list(Account.objects.all())
        
        for i in range(5):  # Create 5 initial positions
            position = self._create_position(
                symbol=self.currency_pairs[i],
                account=random.choice(accounts)
            )
            self.stdout.write(f'Created position: {position}')

    def _create_position(self, symbol, account):
        quantity = Decimal(str(round(random.uniform(10000, 100000), 2)))
        entry_price = Decimal(str(round(random.uniform(1.0, 2.0), 5)))  # Round to 5 decimal places for forex
        current_price = Decimal(str(round(float(entry_price) * random.uniform(0.95, 1.05), 5)))  # ±5% from entry
        
        return ForexPosition.objects.create(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            position_type=random.choice(['LONG', 'SHORT']),
            account=account,
            trade_date=timezone.now(),
            status='OPEN'
        )

    def _update_random_position(self):
        positions = list(ForexPosition.objects.filter(status='OPEN'))
        if not positions:
            return

        position = random.choice(positions)
        old_price = position.current_price
        
        # Randomly update price (±0.5%) with proper decimal places
        price_change = Decimal(str(round(random.uniform(-0.005, 0.005), 5)))
        position.current_price = Decimal(str(round(float(position.current_price) * float(1 + price_change), 5)))
        position.save()
        
        self.stdout.write(f'Updated {position.symbol}: {old_price} -> {position.current_price}')

        # Occasionally update account balance (10% chance)
        if random.random() < 0.1:
            account = random.choice(list(Account.objects.all()))
            change = Decimal(str(round(random.uniform(-10000, 10000), 2)))
            account.account_balance += change
            account.save()
            self.stdout.write(f'Updated account {account.account_name}: balance change {change}')

        # Occasionally create new position (5% chance)
        if random.random() < 0.05:
            account = random.choice(list(Account.objects.all()))
            symbol = random.choice(self.currency_pairs)
            new_position = self._create_position(symbol, account)
            self.stdout.write(f'Created new position: {new_position}') 