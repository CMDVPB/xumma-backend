from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from axx.models import Load
from lync.models import LoadSecret
from lync.permissions import IsCompanyAdmin
from lync.serializers.lync_load import LoadSecretSerializer
from lync.utils import normalize_sequence



from django.contrib.auth.hashers import check_password
import json


class LoadSecretVerifyView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        sequence = request.data.get("sequence")
        load_uf = request.data.get("load_uf")

        user = request.user
        user_company = get_user_company(user)

        if not sequence:
            return Response({"valid": False})

        stored_hash = user.lync_key_sequence_hash


        if not stored_hash:
            return Response({"valid": False})

        sequence = normalize_sequence(sequence)
        sequence_str = json.dumps(sequence, separators=(",", ":"))
        
        print('2894', sequence, sequence_str)

        if not check_password(sequence_str, stored_hash):
            return Response({"valid": False}, status=403)

        load = Load.objects.filter(
            uf=load_uf,
            company=user_company
        ).first()

        if not load:
            return Response({"valid": False}, status=404)

        secret, _ = LoadSecret.objects.get_or_create(
            load=load,
            company=user_company,
            defaults={"created_by": user}
        )

        return Response({
            "valid": True,
            "payload": secret.payload
        })


class LoadSecretUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, load_uf):

        user = request.user
        user_company = get_user_company(user)

        load = Load.objects.filter(
            uf=load_uf,
            company=user_company
        ).first()

        if not load:
            return Response(status=404)

        secret, _ = LoadSecret.objects.get_or_create(
            load=load,
            company=user_company,
            defaults={"created_by": user}
        )

        payload = request.data.get("payload", {})

        secret.payload = payload
        secret.updated_by = user
        secret.save()

        return Response({
            "payload": secret.payload
        })
    



    permission_classes = [IsCompanyAdmin]

    def get_object(self, uf):

        load = get_object_or_404(
            Load.objects.select_related("company"),
            uf=uf
        )

        obj, _ = LoadSecret.objects.get_or_create(
            load=load,
            company=load.company,
            defaults={
                "payload": {}
            }
        )

        return obj

    def get(self, request, uf):

        obj = self.get_object(uf)

        self.check_object_permissions(request, obj)

        return Response(
            LoadSecretSerializer(obj).data
        )

    def patch(self, request, uf):

        obj = self.get_object(uf)

        self.check_object_permissions(request, obj)

        serializer = LoadSecretSerializer(
            obj,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        serializer.save(
            updated_by=request.user
        )

        return Response(serializer.data)