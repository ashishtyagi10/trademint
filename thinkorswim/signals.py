from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Counterparty, EquityPosition, WebSocketConnection
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime
from django.utils import timezone
from django.core.cache import cache

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

@receiver(post_save, sender=Counterparty)
@receiver(post_save, sender=EquityPosition)
def model_changed(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    
    # Get active connections from cache
    connections_list = cache.get('active_connections', [])
    active_connections = []
    
    if not connections_list:
        # If no connections in cache, try to get from database
        connections = WebSocketConnection.objects.filter(
            last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
        )
        connections_list = [conn.channel_name for conn in connections]
        cache.set('active_connections', connections_list, timeout=300)  # 5 minutes timeout
    
    if connections_list:
        for channel_name in connections_list:
            connection_data = cache.get(f"connection_{channel_name}")
            if connection_data:
                last_seen = datetime.fromisoformat(connection_data['last_seen'])
                if last_seen > timezone.now() - timezone.timedelta(minutes=5):
                    active_connections.append(channel_name)
                else:
                    # Remove stale connection
                    cache.delete(f"connection_{channel_name}")
                    connections_list.remove(channel_name)
            else:
                # Create connection data if it doesn't exist
                connection_data = {
                    'groups': ['thinkorswim_updates'],
                    'last_seen': timezone.now().isoformat()
                }
                cache.set(f"connection_{channel_name}", connection_data, timeout=300)
                active_connections.append(channel_name)
    
    # Update the list of active connections
    cache.set('active_connections', connections_list, timeout=300)
    
    if not active_connections:
        return

    if isinstance(instance, Counterparty):
        data = {
            'type': 'counterparty_update',
            'counterparty': {
                'counterparty_id': instance.id,
                'counterparty_name': instance.name,
                'status': 'ACTIVE' if instance.active else 'INACTIVE',
                'counterparty_type': instance.counterparty_type,
                'credit_rating': instance.credit_rating,
                'risk_score': instance.risk_score,
                'created_at': instance.created_at.isoformat(),
                'updated_at': instance.updated_at.isoformat()
            }
        }
    else:  # EquityPosition
        data = {
            'type': 'position_update',
            'position': {
                'position_id': instance.id,
                'symbol': instance.symbol,
                'company_name': instance.company_name,
                'quantity': str(instance.quantity),
                'price': str(instance.entry_price),
                'current_market_price': str(instance.current_price) if instance.current_price else None,
                'status': instance.status,
                'position_type': instance.position_type,
                'trade_date': instance.trade_date.isoformat(),
                'counterparty_name': instance.counterparty.name
            }
        }

    async_to_sync(channel_layer.group_send)(
        'thinkorswim_updates',
        {
            'type': 'thinkorswim.update',
            'data': json.dumps(data, cls=DateTimeEncoder)
        }
    ) 