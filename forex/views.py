from django.shortcuts import render
from django.http import HttpResponse, StreamingHttpResponse
from django.core.paginator import Paginator
from .models import Account, ForexPosition
from django.db.models import signals
import json
import asyncio
from asgiref.sync import sync_to_async
from django.core.serializers import serialize
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Create your views here.
def index(request):
    return render(request, 'forex/index.html')

class ForexEventStream:
    def __init__(self):
        self.clients = set()

    async def register(self, client):
        self.clients.add(client)

    async def unregister(self, client):
        self.clients.remove(client)

    async def broadcast(self, data):
        for client in self.clients.copy():
            try:
                await client.put(data)
            except:
                await self.unregister(client)

# Create a global instance
forex_stream = ForexEventStream()

# Signal handlers
@receiver(post_save, sender=Account)
@receiver(post_save, sender=ForexPosition)
def model_changed(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    
    if isinstance(instance, Account):
        data = {
            'type': 'account_update',
            'account': {
                'account_name': instance.account_name,
                'account_balance': str(instance.account_balance),
                'base_currency': instance.base_currency,
                'is_active': instance.is_active,
                'updated_at': instance.updated_at.isoformat()
            }
        }
    else:  # ForexPosition
        data = {
            'type': 'position_update',
            'position': {
                'currency_pair': instance.currency_pair,
                'buy_sell_indicator': instance.buy_sell_indicator,
                'quantity': str(instance.quantity),
                'price': str(instance.price),
                'current_market_price': str(instance.current_market_price),
                'status': instance.status,
                'trade_date': instance.trade_date.isoformat(),
                'account_name': instance.account.account_name
            }
        }

    async_to_sync(channel_layer.group_send)(
        'forex_updates',
        {
            'type': 'forex.update',
            'data': json.dumps(data)
        }
    )

async def sse_handler(request):
    client_queue = asyncio.Queue()
    await forex_stream.register(client_queue)

    async def event_stream():
        try:
            while True:
                data = await client_queue.get()
                yield f"data: {data}\n\n"
        except:
            await forex_stream.unregister(client_queue)

    return StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
