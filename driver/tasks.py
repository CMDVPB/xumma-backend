
from driver.serializers import TripStopSerializer
from xumma.celery import app
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@app.task(bind=True, max_retries=10, default_retry_delay=1)
def broadcast_trip_stop_visibility(self, company_id, stop):
    try:
        channel_layer = get_channel_layer()
        group_name = f"company_{company_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "forward_trip_stop",
                "payload": {
                    "type": "trip_stop_updated",
                    "data": TripStopSerializer(stop).data,
                }
            },
        )

    except Exception as exc:
        raise self.retry(exc=exc)
