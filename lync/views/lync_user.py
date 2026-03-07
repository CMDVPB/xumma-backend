from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password, check_password
import json

from lync.utils import normalize_sequence


class LyncSequenceVerifyView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        sequence = request.data.get("sequence")
        user = request.user

        if not sequence:
            return Response({"valid": False})

        stored_hash = user.lync_key_sequence_hash

        if not stored_hash:
            return Response({"valid": False})

        sequence = normalize_sequence(sequence)
        sequence_str = json.dumps(sequence, separators=(",", ":"))

        if not check_password(sequence_str, stored_hash):
            return Response({"valid": False})

        return Response({"valid": True})


class UserLyncSequenceView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request):

        user = request.user
        sequence = request.data.get("sequence", [])

        if not isinstance(sequence, list):
            return Response({"error": "Invalid sequence"}, status=400)

        # normalize keys
        sequence = normalize_sequence(sequence)

        if len(sequence) < 3:
            return Response({"error": "Sequence too short"}, status=400)

        # always use the same JSON format
        sequence_str = json.dumps(sequence, separators=(",", ":"))

        print('3060', sequence_str)

        user.lync_key_sequence_hash = make_password(sequence_str)

        user.save(update_fields=["lync_key_sequence_hash"])

        return Response({"success": True})