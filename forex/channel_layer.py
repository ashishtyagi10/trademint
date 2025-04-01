from channels.layers import get_channel_layer

# Create a singleton channel layer instance
_channel_layer = None

def get_shared_channel_layer():
    global _channel_layer
    if _channel_layer is None:
        _channel_layer = get_channel_layer()
    return _channel_layer 