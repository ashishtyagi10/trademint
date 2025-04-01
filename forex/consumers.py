import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from datetime import datetime
from django.conf import settings
from .models import WebSocketConnection
from django.utils import timezone
from django.core.cache import cache
from .channel_layer import get_shared_channel_layer

class ForexSSEConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            print("\nSSE Consumer: New connection established")
            
            # Get the shared channel layer
            self.channel_layer = get_shared_channel_layer()
            
            # Use a consistent channel name
            self.channel_name = "forex_stream"
            print(f"SSE Consumer: Using channel name: {self.channel_name}")
            
            # Add to groups before sending initial data
            print("\nSSE Consumer: Adding to groups...")
            
            # Add to forex_updates group
            await self.channel_layer.group_add("forex_updates", self.channel_name)
            self.groups.append("forex_updates")
            print(f"SSE Consumer: Added to forex_updates group")
            
            # Add to account_updates group
            await self.channel_layer.group_add("account_updates", self.channel_name)
            self.groups.append("account_updates")
            print(f"SSE Consumer: Added to account_updates group")
            
            # Add to position_updates group
            await self.channel_layer.group_add("position_updates", self.channel_name)
            self.groups.append("position_updates")
            print(f"SSE Consumer: Added to position_updates group")
            
            # Accept the connection first
            await self.accept()
            print("SSE Consumer: Connection accepted")

            # Store connection info in cache
            await self.store_connection_info()
            
            # Send initial data
            try:
                await self.send_initial_data()
                print("SSE Consumer: Successfully sent initial data")
            except Exception as e:
                print(f"SSE Consumer: Error sending initial data: {e}")
                import traceback
                print(traceback.format_exc())

            # Start the ping loop and message check loop
            asyncio.create_task(self.ping_loop())
            asyncio.create_task(self.check_for_messages())
            print("SSE Consumer: Ping and message check loops started")
            
        except Exception as e:
            print(f"SSE Consumer: Error in connect: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    async def disconnect(self, close_code):
        try:
            print("\nSSE Consumer: Disconnecting...")
            
            if hasattr(self, 'channel_layer'):
                # Remove from all groups
                for group in self.groups:
                    await self.channel_layer.group_discard(group, self.channel_name)
                    print(f"SSE Consumer: Removed from group: {group}")
                
                # Remove connection info from cache
                await self.remove_connection_info()
                
                print("SSE Consumer: Disconnected successfully")
        except Exception as e:
            print(f"SSE Consumer: Error during disconnect: {e}")
            import traceback
            print(traceback.format_exc())

    async def check_for_messages(self):
        """Check for new messages in the cache"""
        while True:
            try:
                print("\nSSE Consumer: Checking cache for messages")
                print(f"SSE Consumer: Channel name: {self.channel_name}")
                
                # Create cache key
                cache_key = f"forex_message_{self.channel_name}"
                print(f"SSE Consumer: Cache key being checked: {cache_key}")
                
                # Get message from cache using sync_to_async
                message_json = await self.get_message_from_cache(cache_key)
                
                if message_json:
                    try:
                        message = json.loads(message_json)
                        print(f"SSE Consumer: Found message: {message}")
                        
                        # Send the message to the client
                        await self.send(text_data=json.dumps(message))
                        print(f"SSE Consumer: Message sent to client: {message}")
                        
                        # Delete the message from cache
                        await self.delete_message_from_cache(cache_key)
                        print(f"SSE Consumer: Deleted message from cache for key: {cache_key}")
                    except json.JSONDecodeError as e:
                        print(f"SSE Consumer: Error decoding message: {e}")
                        # Delete invalid message from cache
                        await self.delete_message_from_cache(cache_key)
                        print(f"SSE Consumer: Deleted invalid message from cache for key: {cache_key}")
                else:
                    print(f"SSE Consumer: No messages found in cache for key: {cache_key}")
                
                # Wait before checking again
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"SSE Consumer: Error in message check loop: {e}")
                import traceback
                print(traceback.format_exc())
                await asyncio.sleep(1)

    @database_sync_to_async
    def get_message_from_cache(self, cache_key):
        """Get message from cache"""
        return cache.get(cache_key)

    @database_sync_to_async
    def delete_message_from_cache(self, cache_key):
        """Delete message from cache"""
        cache.delete(cache_key)

    @database_sync_to_async
    def store_connection_info(self):
        """Store connection info in cache"""
        # Store connection data
        cache_key = f"connection_{self.channel_name}"
        cache.set(cache_key, {
            'groups': self.groups,
            'last_seen': timezone.now().isoformat()
        }, timeout=300)  # 5 minutes timeout
        
        # Add to active connections list
        connections_list = cache.get('active_connections', [])
        if self.channel_name not in connections_list:
            connections_list.append(self.channel_name)
            cache.set('active_connections', connections_list, timeout=300)  # 5 minutes timeout
        
        print(f"SSE Consumer: Stored connection info in cache for channel: {self.channel_name}")
        print(f"SSE Consumer: Active connections: {connections_list}")

    @database_sync_to_async
    def update_connection_info(self):
        """Update connection info in cache"""
        # Update connection data
        cache_key = f"connection_{self.channel_name}"
        cache.set(cache_key, {
            'groups': self.groups,
            'last_seen': timezone.now().isoformat()
        }, timeout=300)  # 5 minutes timeout
        print(f"SSE Consumer: Updated connection info in cache for channel: {self.channel_name}")

    @database_sync_to_async
    def remove_connection_info(self):
        """Remove connection info from cache"""
        # Remove connection data
        cache_key = f"connection_{self.channel_name}"
        cache.delete(cache_key)
        
        # Remove from active connections list
        connections_list = cache.get('active_connections', [])
        if self.channel_name in connections_list:
            connections_list.remove(self.channel_name)
            cache.set('active_connections', connections_list, timeout=300)  # 5 minutes timeout
        
        print(f"SSE Consumer: Removed connection info from cache for channel: {self.channel_name}")

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

        print("\nSSE Consumer: Initial data preparation")
        print(f"SSE Consumer: Found {len(accounts)} accounts and {len(positions)} positions")

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
            # Rename account__account_name to account_name for DataTables
            position['account_name'] = position.pop('account__account_name')
            position['position_id'] = position['id']
            
            # Debug log for each position
            print(f"\nSSE Consumer: Position {position['id']} data:")
            print(f"  Symbol: {position['symbol']}")
            print(f"  Account name: {position['account_name']}")
            print(f"  All fields: {list(position.keys())}")

        return {
            'accounts': accounts,
            'positions': positions
        }

    async def send_initial_data(self):
        try:
            data = await self.get_initial_data()
            print(f"Sending initial data with {len(data['accounts'])} accounts and {len(data['positions'])} positions")
            await self.send(text_data=json.dumps(data))
        except Exception as e:
            print(f"Error sending initial data: {e}")

    @classmethod
    async def broadcast(cls, event_data):
        """Broadcast updates to all connected clients"""
        print(f"Broadcasting update: {event_data}")  # Debug log
        for consumer in cls.consumers.copy():
            try:
                await consumer.send(text_data=json.dumps(event_data))
            except Exception as e:
                print(f"Error sending to consumer: {e}")
                continue

    async def debug_message(self, event):
        """Handle debug messages"""
        print("\nSSE Consumer: Received debug message")
        print(f"SSE Consumer: Event data: {event}")
        print(f"SSE Consumer: Channel name: {self.channel_name}")
        print(f"SSE Consumer: Current groups: {self.groups}")
        
        try:
            # Send the debug message to the client
            await self.send(text_data=json.dumps(event))
            print("SSE Consumer: Successfully sent debug message to client")
        except Exception as e:
            print(f"SSE Consumer: Error sending debug message to client: {e}")
            import traceback
            print(traceback.format_exc())

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages from the client"""
        print("\nSSE Consumer: Received message from client")
        print(f"SSE Consumer: Text data: {text_data}")
        print(f"SSE Consumer: Bytes data: {bytes_data}")
        
        if text_data:
            try:
                data = json.loads(text_data)
                print(f"SSE Consumer: Parsed JSON data: {data}")
            except json.JSONDecodeError as e:
                print(f"SSE Consumer: Error parsing JSON: {e}")
        else:
            print("SSE Consumer: No text data received")

    async def handle_message(self, event):
        """Catch-all message handler for debugging"""
        print("\nSSE Consumer: Received event in handle_message")
        print(f"SSE Consumer: Event type: {event.get('type')}")
        print(f"SSE Consumer: Event data: {event.get('data')}")
        print(f"SSE Consumer: Channel name: {self.channel_name}")
        print(f"SSE Consumer: Current groups: {self.groups}")
        
        try:
            # Send the event data back to the client
            await self.send(text_data=json.dumps(event))
            print("SSE Consumer: Successfully sent event data to client")
        except Exception as e:
            print(f"SSE Consumer: Error sending event data to client: {e}")
            import traceback
            print(traceback.format_exc())

    async def ping_loop(self):
        while True:
            try:
                # Send ping every 10 seconds
                ping_message = json.dumps({"type": "ping"})
                await self.send(text_data=ping_message)
                print("SSE Consumer: Sent ping")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"SSE Consumer Error in ping loop: {e}")
                import traceback
                print(traceback.format_exc())
                break

    @database_sync_to_async
    def get_active_connections_count(self):
        """Get count of active connections from database"""
        return WebSocketConnection.objects.filter(
            last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()

    async def account_update(self, event):
        """Handle account update events"""
        print("\nSSE Consumer: Received account update event")
        print(f"SSE Consumer: Event data: {event}")
        print(f"SSE Consumer: Channel name: {self.channel_name}")
        print(f"SSE Consumer: Current groups: {self.groups}")
        
        try:
            # Send the account update to the client
            await self.send(text_data=json.dumps(event))
            print("SSE Consumer: Successfully sent account update to client")
        except Exception as e:
            print(f"SSE Consumer: Error sending account update to client: {e}")
            import traceback
            print(traceback.format_exc())

    async def position_update(self, event):
        """Handle position update events"""
        print("\nSSE Consumer: Received position update event")
        print(f"SSE Consumer: Event data: {event}")
        print(f"SSE Consumer: Channel name: {self.channel_name}")
        print(f"SSE Consumer: Current groups: {self.groups}")
        
        try:
            # Send the position update to the client
            await self.send(text_data=json.dumps(event))
            print("SSE Consumer: Successfully sent position update to client")
        except Exception as e:
            print(f"SSE Consumer: Error sending position update to client: {e}")
            import traceback
            print(traceback.format_exc()) 