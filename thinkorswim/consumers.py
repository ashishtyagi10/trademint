import json
import asyncio
import weakref
from channels.generic.http import AsyncHttpConsumer
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from datetime import datetime
from django.conf import settings
from .models import WebSocketConnection
from django.utils import timezone
from django.core.cache import cache

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class ThinkOrSwimSSEConsumer(AsyncHttpConsumer):
    consumers = weakref.WeakSet()

    async def handle(self, body):
        print("SSE Consumer: New connection established")
        await self.send_headers(headers=[
            (b"Cache-Control", b"no-cache"),
            (b"Content-Type", b"text/event-stream"),
            (b"Connection", b"keep-alive"),
        ])

        self.channel_layer = get_channel_layer()
        await self.channel_layer.group_add("thinkorswim_updates", self.channel_name)
        print("SSE Consumer: Added to thinkorswim_updates group")

        # Add self to consumers set
        self.__class__.consumers.add(self)

        # Store connection info
        await self.store_connection_info()

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
    def store_connection_info(self):
        """Store connection info in database"""
        WebSocketConnection.objects.update_or_create(
            channel_name=self.channel_name,
            defaults={
                'groups': ['thinkorswim_updates'],
                'last_seen': timezone.now()
            }
        )

    @database_sync_to_async
    def remove_connection_info(self):
        """Remove connection info from database"""
        WebSocketConnection.objects.filter(channel_name=self.channel_name).delete()

    @database_sync_to_async
    def get_initial_data(self):
        # Import models here to avoid app registry issues
        from .models import Counterparty, EquityPosition
        
        counterparties = list(Counterparty.objects.values(
            'id',
            'name',
            'active',
            'counterparty_type',
            'credit_rating',
            'risk_score',
            'created_at',
            'updated_at'
        ))

        positions = list(EquityPosition.objects.select_related('counterparty').values(
            'id',
            'symbol',
            'quantity',
            'entry_price',
            'current_price',
            'status',
            'position_type',
            'trade_date',
            'company_name',
            'counterparty__name'
        ))

        # Format dates and decimal values
        for counterparty in counterparties:
            counterparty['created_at'] = counterparty['created_at'].isoformat()
            counterparty['updated_at'] = counterparty['updated_at'].isoformat()
            counterparty['counterparty_name'] = counterparty.pop('name')
            counterparty['counterparty_id'] = counterparty['id']
            counterparty['status'] = 'ACTIVE' if counterparty['active'] else 'INACTIVE'

        for position in positions:
            position['entry_price'] = str(position['entry_price'])
            position['current_price'] = str(position['current_price']) if position['current_price'] else None
            position['quantity'] = str(position['quantity'])
            position['trade_date'] = position['trade_date'].isoformat()
            position['counterparty_name'] = position.pop('counterparty__name')
            position['position_id'] = position['id']

        return {
            'counterparties': counterparties,
            'positions': positions
        }

    async def send_initial_data(self):
        try:
            data = await self.get_initial_data()
            print(f"Sending initial data with {len(data['counterparties'])} counterparties and {len(data['positions'])} positions")
            await self.send_body(
                f"data: {json.dumps(data, cls=DateTimeEncoder)}\n\n".encode('utf-8'),
                more_body=True
            )
        except Exception as e:
            print(f"Error sending initial data: {e}")

    async def thinkorswim_update(self, event):
        await self.send_body(f"data: {event['data']}\n\n".encode('utf-8'), more_body=True)

    async def disconnect(self):
        if hasattr(self, 'channel_layer'):
            await self.channel_layer.group_discard("thinkorswim_updates", self.channel_name)
            self.__class__.consumers.discard(self)
            await self.remove_connection_info()
            print("Client disconnected from thinkorswim updates")

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