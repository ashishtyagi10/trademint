from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Account, ForexPosition
import json
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

@receiver(post_save, sender=Account)
@receiver(post_save, sender=ForexPosition)
def model_changed(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    
    if isinstance(instance, Account):
        data = {
            'type': 'account_update',
            'account': {
                'id': instance.id,
                'name': instance.account_name,
                'account_balance': str(instance.account_balance),
                'base_currency': instance.base_currency,
                'is_active': instance.is_active,
                'created_at': instance.created_at.isoformat(),
                'updated_at': instance.updated_at.isoformat()
            }
        }
    else:  # ForexPosition
        data = {
            'type': 'position_update',
            'position': {
                'id': instance.id,
                'symbol': instance.symbol,
                'quantity': str(instance.quantity),
                'entry_price': str(instance.entry_price),
                'current_price': str(instance.current_price),
                'status': instance.status,
                'position_type': instance.position_type,
                'trade_date': instance.trade_date.isoformat(),
                'account_name': instance.account.account_name,
                'account_id': instance.account.id
            }
        }

    async_to_sync(channel_layer.group_send)(
        'forex_updates',
        {
            'type': 'forex.update',
            'data': json.dumps(data, cls=DateTimeEncoder)
        }
    ) 