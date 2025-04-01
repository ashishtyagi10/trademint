import random
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import asyncio
import django
import os
from threading import Thread
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
import json
from forex.consumers import ForexSSEConsumer

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trademint.settings')
django.setup()

from forex.models import Account, ForexPosition

class DataGenerator:
    CURRENCY_PAIRS = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD']
    ACCOUNT_NAMES = ['Trading Account', 'Investment Fund', 'Hedge Fund', 'Personal Account', 'Corporate Account']
    
    def __init__(self, interval=5):
        """Initialize generator with interval in seconds"""
        self.interval = interval
        self.is_running = False
        self.thread = None
        self.loop = None

    def start(self):
        """Start the data generation in a separate thread"""
        if not self.is_running:
            self.is_running = True
            self.thread = Thread(target=self._run_async_loop)
            self.thread.daemon = True
            self.thread.start()
            print("Data generator started")

    def stop(self):
        """Stop the data generation"""
        self.is_running = False
        if self.thread:
            self.thread.join()
            print("Data generator stopped")

    def _run_async_loop(self):
        """Run the async event loop in the thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._generate_data())
        finally:
            self.loop.close()

    @database_sync_to_async
    def _serialize_position(self, position):
        return {
            "position_id": position.id,
            "account_id": position.account.id,
            "currency_pair": position.currency_pair,
            "trade_date": position.trade_date.isoformat(),
            "settlement_date": position.settlement_date.isoformat(),
            "buy_sell_indicator": position.buy_sell_indicator,
            "quantity": str(position.quantity),
            "price": str(position.price),
            "status": position.status,
            "exchange": position.exchange,
            "counterparty": position.counterparty,
            "current_market_price": str(position.current_market_price) if position.current_market_price else None
        }

    async def _broadcast_update(self, data):
        try:
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                "forex_updates",
                {
                    "type": "forex.update",
                    "data": json.dumps(data)
                }
            )
        except Exception as e:
            print(f"Broadcast error: {str(e)}")

    async def _generate_data(self):
        """Main data generation loop"""
        while self.is_running:
            try:
                # Randomly choose to create new account or position
                if random.random() < 0.3:  # 30% chance to create account
                    account = await self._create_random_account()
                    if account:
                        await self._broadcast_update({
                            "type": "account_update",
                            "account": {
                                "account_id": account.id,
                                "account_name": account.account_name
                            }
                        })
                else:  # 70% chance to create/update position
                    await self._handle_random_position()

                # Wait for the specified interval
                await asyncio.sleep(self.interval)
            except Exception as e:
                print(f"Generation error: {str(e)}")
                await asyncio.sleep(1)

    @database_sync_to_async
    def _create_random_account(self):
        """Create a random account"""
        name = f"{random.choice(self.ACCOUNT_NAMES)} {random.randint(1000, 9999)}"
        account = Account.objects.create(account_name=name)
        print(f"Created account: {name}")
        return account

    async def _handle_random_position(self):
        """Create or update a random position"""
        try:
            # Get a random account
            accounts_exist = await self._check_accounts_exist()
            if not accounts_exist:
                await self._create_random_account()
                return

            account = await self._get_random_account()
            
            # Decide whether to create new position or update existing
            positions_exist = await self._check_positions_exist()
            if random.random() < 0.7 or not positions_exist:  # 70% chance for new position
                position = await self._create_random_position(account)
                if position:
                    position_data = await self._serialize_position(position)
                    await self._broadcast_update({
                        "type": "position_update",
                        "position": position_data
                    })
            else:
                position = await self._update_random_position()
                if position:
                    position_data = await self._serialize_position(position)
                    await self._broadcast_update({
                        "type": "position_update",
                        "position": position_data
                    })

        except Exception as e:
            print(f"Position handling error: {str(e)}")

    @database_sync_to_async
    def _check_accounts_exist(self):
        return Account.objects.exists()

    @database_sync_to_async
    def _check_positions_exist(self):
        return ForexPosition.objects.exists()

    @database_sync_to_async
    def _get_random_account(self):
        return Account.objects.order_by('?').first()

    @database_sync_to_async
    def _create_random_position(self, account):
        """Create a random forex position"""
        position = ForexPosition.objects.create(
            account=account,
            currency_pair=random.choice(self.CURRENCY_PAIRS),
            trade_date=timezone.now(),
            settlement_date=timezone.now() + timedelta(days=2),
            buy_sell_indicator=random.choice(['B', 'S']),
            quantity=Decimal(str(random.randint(1000, 100000))),
            price=Decimal(str(round(random.uniform(0.5, 2.0), 4))),
            status=random.choice(['OPEN', 'PENDING', 'PARTIALLY_CLOSED']),
            exchange='FOREX',
            counterparty=f'Bank{random.randint(1, 5)}',
            current_market_price=Decimal(str(round(random.uniform(0.5, 2.0), 4)))
        )
        print(f"Created position: {position}")
        return position

    @database_sync_to_async
    def _update_random_position(self):
        """Update a random existing position"""
        try:
            position = ForexPosition.objects.order_by('?').first()
            if position:
                # Update price and calculate P/L
                new_price = Decimal(str(round(float(position.price) * random.uniform(0.95, 1.05), 4)))
                position.current_market_price = new_price
                position.save()
                print(f"Updated position: {position}")
                return position
            return None
        except Exception as e:
            print(f"Error updating position: {e}")
            return None

# Usage example
if __name__ == "__main__":
    generator = DataGenerator(interval=5)
    generator.start()
    
    try:
        # Keep the main thread alive
        while True:
            asyncio.sleep(1)
    except KeyboardInterrupt:
        generator.stop()
