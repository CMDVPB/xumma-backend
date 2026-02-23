
from axx.models import Trip
from driver.models import TripStop
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


@app.task(bind=True, max_retries=10, default_retry_delay=1)
def broadcast_trip_stop_reorder(self, trip_uf):
    try:
        channel_layer = get_channel_layer()

        trip = Trip.objects.get(uf=trip_uf)

        stops = list(
            TripStop.objects
            .filter(trip=trip)
            .order_by("order")
            .values_list("uf", flat=True)
        )

        async_to_sync(channel_layer.group_send)(
            f"company_{trip.company_id}",
            {
                "type": "forward_trip_stop",
                "payload": {
                    "type": "trip_stop_reordered",
                    "action": "reordered",   # IMPORTANT
                    "data": {
                        "trip_uf": trip_uf,
                        "ordered_ufs": stops,
                        "stops_version": trip.stops_version,
                    }
                }
            },
        )

    except Exception as exc:
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=10, default_retry_delay=1)
def broadcast_trip_stop_messages_read(self, company_id, trip_stop_uf):
    try:
        channel_layer = get_channel_layer()
        group_name = f"company_{company_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "forward_trip_stop_messages_read",
                "payload": {
                    "type": "trip_stop_messages_read",
                    "trip_stop_uf": trip_stop_uf,
                },
            },
        )

    except Exception as exc:
        raise self.retry(exc=exc)
