import json
import asyncio
import weakref
from channels.generic.http import AsyncHttpConsumer
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from datetime import datetime

class ForexSSEConsumer(AsyncHttpConsumer):
    consumers = weakref.WeakSet()

    async def handle(self, body):
        print("SSE Consumer: New connection established")
        await self.send_headers(headers=[
            (b"Cache-Control", b"no-cache"),
            (b"Content-Type", b"text/event-stream"),
            (b"Connection", b"keep-alive"),
        ])

        self.channel_layer = get_channel_layer()
        await self.channel_layer.group_add("forex_updates", self.channel_name)
        print("SSE Consumer: Added to forex_updates group")

        # Add self to consumers set
        self.__class__.consumers.add(self)

        # Send initial data
        await self.send_initial_data()

        # Keep the connection alive
        while True:
            try:
                ping_message = json.dumps({"type": "ping"})
                await self.send_body(f"data: {ping_message}\n\n".encode('utf-8'), more_body=True)
                print("SSE Consumer: Sent ping")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"SSE Consumer Error in handle: {e}")
                break

    @database_sync_to_async
    def get_initial_data(self):
        # Import models here to avoid app registry issues
        from .models import Account, ForexPosition
        
        accounts = list(Account.objects.values(
            'id',
            'account_name',
            'account_balance',
            'base_currency',
            'is_active',
            'created_at',
            'updated_at'
        ))

        positions = list(ForexPosition.objects.select_related('account').values(
            'id',
            'symbol',
            'quantity',
            'entry_price',
            'current_price',
            'status',
            'position_type',
            'trade_date',
            'account__account_name'
        ))

        # Format dates and decimal values
        for account in accounts:
            account['created_at'] = account['created_at'].isoformat()
            account['updated_at'] = account['updated_at'].isoformat()
            account['account_balance'] = str(account['account_balance'])
            account['name'] = account.pop('account_name')

        for position in positions:
            position['entry_price'] = str(position['entry_price'])
            position['current_price'] = str(position['current_price']) if position['current_price'] else None
            position['quantity'] = str(position['quantity'])
            position['trade_date'] = position['trade_date'].isoformat()
            position['account_name'] = position.pop('account__account_name')
            position['position_id'] = position['id']

        return {
            'accounts': accounts,
            'positions': positions
        }

    async def send_initial_data(self):
        try:
            data = await self.get_initial_data()
            print(f"Sending initial data with {len(data['accounts'])} accounts and {len(data['positions'])} positions")
            await self.send_body(
                f"data: {json.dumps(data)}\n\n".encode('utf-8'),
                more_body=True
            )
        except Exception as e:
            print(f"Error sending initial data: {e}")

    async def forex_update(self, event):
        await self.send_body(f"data: {event['data']}\n\n".encode('utf-8'), more_body=True)

    async def disconnect(self):
        if hasattr(self, 'channel_layer'):
            await self.channel_layer.group_discard("forex_updates", self.channel_name)
            self.__class__.consumers.discard(self)
            print("Client disconnected from forex updates")

    @classmethod
    async def broadcast(cls, event_data):
        """Broadcast updates to all connected clients"""
        print(f"Broadcasting update: {event_data}")  # Debug log
        for consumer in cls.consumers.copy():
            try:
                await consumer.send_body(
                    f"data: {json.dumps(event_data)}\n\n".encode('utf-8'),
                    more_body=True
                )
            except Exception as e:
                print(f"Error sending to consumer: {e}")
                continue 