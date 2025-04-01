from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Account, ForexPosition, WebSocketConnection
from django.utils import timezone
from django.core.cache import cache
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

@receiver(post_save)
def model_changed(sender, instance, created, **kwargs):
    try:
        # Only handle Account and ForexPosition models
        if sender not in [Account, ForexPosition]:
            return

        print("\nSignal Handler: Model changed")
        print(f"Signal Handler: Model: {sender.__name__}")
        print(f"Signal Handler: Instance: {instance}")
        print(f"Signal Handler: Created: {created}")

        # Get active connections from cache
        active_connections = []
        connections_list = cache.get('active_connections', [])
        
        # If no connections exist, create a new one
        if not connections_list:
            channel_name = "forex_stream"  # Use a simple, consistent channel name
            connections_list = [channel_name]
            cache.set('active_connections', connections_list, timeout=300)  # 5 minutes timeout
            print(f"Signal Handler: Created new connection: {channel_name}")
            
            # Create connection data
            connection_data = {
                'groups': ['forex_updates', 'account_updates', 'position_updates'],
                'last_seen': timezone.now().isoformat()
            }
            cache.set(f"connection_{channel_name}", connection_data, timeout=300)
            print(f"Signal Handler: Created connection data for: {channel_name}")
            
            active_connections = [channel_name]
        else:
            print(f"Signal Handler: Found {len(connections_list)} connections in cache")
            
            for channel_name in connections_list:
                connection_data = cache.get(f"connection_{channel_name}")
                if connection_data:
                    last_seen = datetime.fromisoformat(connection_data['last_seen'])
                    if last_seen > timezone.now() - timezone.timedelta(minutes=5):
                        active_connections.append(channel_name)
                        print(f"Signal Handler: Found active connection: {channel_name}")
                    else:
                        # Remove stale connection
                        cache.delete(f"connection_{channel_name}")
                        connections_list.remove(channel_name)
                        print(f"Signal Handler: Removed stale connection: {channel_name}")
                else:
                    # Create connection data if it doesn't exist
                    connection_data = {
                        'groups': ['forex_updates', 'account_updates', 'position_updates'],
                        'last_seen': timezone.now().isoformat()
                    }
                    cache.set(f"connection_{channel_name}", connection_data, timeout=300)
                    print(f"Signal Handler: Created connection data for: {channel_name}")
                    active_connections.append(channel_name)
                    print(f"Signal Handler: Added connection to active list: {channel_name}")
        
        # Update the list of active connections
        cache.set('active_connections', connections_list, timeout=300)  # 5 minutes timeout
        
        if not active_connections:
            print("Signal Handler: No active connections found")
            return

        print(f"Signal Handler: Found {len(active_connections)} active connections")
        
        # Prepare the message based on the model type
        if isinstance(instance, Account):
            message_type = 'account_update'
            data = {
                'id': instance.id,
                'name': instance.account_name,
                'balance': float(instance.account_balance),
                'currency': instance.base_currency,
                'is_active': instance.is_active,
                'last_updated': instance.updated_at.isoformat()
            }
        else:  # ForexPosition
            message_type = 'position_update'
            data = {
                'id': instance.id,
                'account_id': instance.account.id,
                'symbol': instance.symbol,
                'position_type': instance.position_type,
                'quantity': float(instance.quantity),
                'entry_price': float(instance.entry_price),
                'current_price': float(instance.current_price) if instance.current_price else None,
                'profit_loss': float(instance.calculate_pnl()),
                'status': instance.status,
                'trade_date': instance.trade_date.isoformat(),
                'last_updated': instance.updated_at.isoformat(),
                'account_name': instance.account.account_name
            }

        # Store the message in cache for each active connection
        message = {
            'type': message_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }

        for channel_name in active_connections:
            try:
                # Store message in cache with a unique key for each connection
                cache_key = f"forex_message_{channel_name}"
                message_json = json.dumps(message)
                cache.set(cache_key, message_json, timeout=60)  # Message expires after 60 seconds
                print(f"Signal Handler: Stored message in cache for channel {channel_name}")
                print(f"Signal Handler: Cache key used: {cache_key}")
                print(f"Signal Handler: Message stored: {message_json}")
                
                # Verify the message was stored
                stored_message = cache.get(cache_key)
                if stored_message:
                    print(f"Signal Handler: Verified message in cache for key {cache_key}")
                else:
                    print(f"Signal Handler: WARNING - Message not found in cache for key {cache_key}")
            except Exception as e:
                print(f"Signal Handler: Error storing message in cache for connection {channel_name}: {e}")
                import traceback
                print(traceback.format_exc())

    except Exception as e:
        print(f"Signal Handler: Error in model_changed: {e}")
        import traceback
        print(traceback.format_exc()) 