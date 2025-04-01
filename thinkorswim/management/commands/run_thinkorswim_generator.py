import django
django.setup()

from django.core.management.base import BaseCommand
from thinkorswim.models import Counterparty, EquityPosition
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import random
from decimal import Decimal
import time
import json
from datetime import datetime
from django.utils import timezone

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class Command(BaseCommand):
    help = 'Generates random ThinkOrSwim data'

    def __init__(self):
        super().__init__()
        self.symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD', 'INTC', 'IBM']
        self.companies = ['Apple Inc', 'Alphabet Inc', 'Microsoft Corp', 'Amazon.com Inc', 'Meta Platforms Inc', 
                         'Tesla Inc', 'NVIDIA Corp', 'Advanced Micro Devices Inc', 'Intel Corp', 'IBM Corp']
        self.channel_layer = get_channel_layer()

    def handle(self, *args, **options):
        self.stdout.write('Starting ThinkOrSwim data generator...')
        self._ensure_initial_data()
        
        while True:
            try:
                self._update_random_position()
                time.sleep(5)  # Update every 5 seconds
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS('Generator stopped'))
                break

    def _ensure_initial_data(self):
        if Counterparty.objects.count() == 0:
            self._create_initial_counterparties()
        
        if EquityPosition.objects.count() == 0:
            self._create_initial_positions()

    def _create_initial_counterparties(self):
        counterparties = [
            ('Goldman Sachs', 'BANK', 'AA+', 95),
            ('Morgan Stanley', 'BANK', 'AA', 92),
            ('JP Morgan', 'BANK', 'AAA', 98),
            ('Citadel', 'HEDGE_FUND', 'AA', 90),
            ('BlackRock', 'ASSET_MANAGER', 'AAA', 97)
        ]

        for name, c_type, rating, score in counterparties:
            Counterparty.objects.create(
                name=name,
                counterparty_type=c_type,
                credit_rating=rating,
                risk_score=score,
                active=True
            )
        self.stdout.write(self.style.SUCCESS('Created initial counterparties'))

    def _create_initial_positions(self):
        counterparties = list(Counterparty.objects.all())
        
        for i in range(5):  # Create 5 initial positions
            position = self._create_position(
                symbol=self.symbols[i],
                company_name=self.companies[i],
                counterparty=random.choice(counterparties)
            )
            self.stdout.write(f'Created position: {position}')

    def _create_position(self, symbol, company_name, counterparty):
        quantity = Decimal(str(random.randint(100, 1000)))
        entry_price = Decimal(str(random.uniform(50, 500)))
        current_price = entry_price * Decimal(str(random.uniform(0.95, 1.05)))  # ±5% from entry
        
        return EquityPosition.objects.create(
            symbol=symbol,
            company_name=company_name,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            position_type=random.choice(['LONG', 'SHORT']),
            counterparty=counterparty,
            trade_date=timezone.now(),
            status='OPEN'
        )

    def _update_random_position(self):
        positions = list(EquityPosition.objects.filter(status='OPEN'))
        if not positions:
            return

        position = random.choice(positions)
        old_price = position.current_price
        
        # Randomly update price (±2%)
        price_change = Decimal(str(random.uniform(-0.02, 0.02)))
        position.current_price = position.current_price * (1 + price_change)
        position.save()
        
        self.stdout.write(f'Updated {position.symbol}: {old_price} -> {position.current_price}')

        # Occasionally create new position (5% chance)
        if random.random() < 0.05:
            unused_symbols = list(set(self.symbols) - set(p.symbol for p in positions))
            if unused_symbols:
                symbol = random.choice(unused_symbols)
                company_name = self.companies[self.symbols.index(symbol)]
                counterparty = random.choice(list(Counterparty.objects.all()))
                new_position = self._create_position(symbol, company_name, counterparty)
                self.stdout.write(f'Created new position: {new_position}')

    def _broadcast_update(self, update_type, data):
        try:
            async_to_sync(self.channel_layer.group_send)(
                "thinkorswim_updates",
                {
                    "type": "thinkorswim.update",
                    "data": json.dumps({
                        "type": update_type,
                        update_type.split('_')[0]: data
                    })
                }
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error broadcasting update: {str(e)}'))

    def _serialize_position(self, pos):
        return {
            'id': pos.id,
            'symbol': pos.symbol,
            'company_name': pos.company_name,
            'position_type': pos.position_type,
            'quantity': pos.quantity,
            'entry_price': str(pos.entry_price),
            'current_price': str(pos.current_price),
            'status': pos.status,
            'trade_date': pos.trade_date.isoformat(),
            'counterparty_name': pos.counterparty.name,
            'market_value': str(pos.market_value),
            'unrealized_pl': str(pos.unrealized_pl),
            'pl_percentage': str(pos.pl_percentage)
        } 