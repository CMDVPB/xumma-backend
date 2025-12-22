from collections import OrderedDict, defaultdict
from django.core.exceptions import FieldDoesNotExist
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError, SET_NULL, SET_DEFAULT
from django.db.models.fields.related import ForeignObjectRel, ManyToManyRel
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework.exceptions import ValidationError


shall_print = False


class CustomBaseNestedModelSerializer(serializers.ModelSerializer):
    lookup_field = 'uf'

    def _get_existing_instance(self, validated_data):
        model_class = self.Meta.model

        if shall_print:
            print('SR4400', validated_data)

        # Check for both `id` and `uf` in the validated data
        lookup_params = self._get_related_pk(validated_data, model_class)
        if lookup_params:
            return model_class.objects.filter(**lookup_params).first()

        return None

    def _extract_relations(self, validated_data):
        reverse_relations = OrderedDict()
        relations = OrderedDict()

        for field_name, field in self.fields.items():
            if field.read_only:
                continue
            try:
                related_field, direct = self._get_related_field(field)
            except FieldDoesNotExist:
                continue

            if isinstance(field, serializers.ListSerializer) and isinstance(field.child, serializers.ModelSerializer):
                if field.source not in validated_data:
                    continue

                validated_data.pop(field.source)
                reverse_relations[field_name] = (
                    related_field, field.child, field.source)

            if isinstance(field, serializers.ModelSerializer):
                if field.source not in validated_data:
                    continue

                if validated_data.get(field.source) is None:
                    if direct:
                        continue

                validated_data.pop(field.source)

                if direct:
                    relations[field_name] = (field, field.source)
                else:
                    reverse_relations[field_name] = (
                        related_field, field, field.source)

        return relations, reverse_relations

    def _get_related_field(self, field):
        model_class = self.Meta.model

        try:
            related_field = model_class._meta.get_field(field.source)
        except FieldDoesNotExist:
            if field.source.endswith('_set'):
                related_field = model_class._meta.get_field(field.source[:-4])
            else:
                raise

        if isinstance(related_field, ForeignObjectRel) and not isinstance(related_field, ManyToManyRel):
            return related_field.field, False
        return related_field, True

    def _get_related_pk(self, data, model_class):

        if shall_print:
            print('6688', data)

        lookup_field = getattr(self.Meta, 'lookup_field', self.lookup_field)

        if lookup_field in data and data[lookup_field]:
            return {lookup_field: data[lookup_field]}
        return None

    def _get_serializer_for_field(self, field, **kwargs):

        if shall_print:
            print('6730')

        kwargs.update({
            'context': self.context,
            'partial': self.partial if kwargs.get('instance') else False,
        })

        # if field is a polymorphic serializer
        if hasattr(field, '_get_serializer_from_resource_type'):
            # get 'real' serializer based on resource type
            serializer = field._get_serializer_from_resource_type(
                kwargs.get('data').get(field.resource_type_field_name)
            )

            return serializer.__class__(**kwargs)
        else:
            return field.__class__(**kwargs)

    def _get_generic_lookup(self, instance, related_field):
        if shall_print:
            print('6740')

        return {
            related_field.content_type_field_name: ContentType.objects.get_for_model(instance),
            related_field.object_id_field_name: getattr(instance, self.lookup_field),
        }

    def _prefetch_related_instances(self, field, related_data):
        if shall_print:
            print('6750')

        model_class = field.Meta.model
        instances = []

        for data in related_data:
            lookup = self._get_related_pk(data, model_class)
            if lookup:
                instance = model_class.objects.filter(**lookup).first()
                if instance:
                    instances.append(instance)
                else:
                    raise ValidationError(
                        {field.Meta.model.__name__: f"Object with provided `{self.lookup_field}` does not exist."}
                    )

        return instances

    def update_or_create_direct_relations(self, attrs, relations):
        if shall_print:
            print('6760')

        for field_name, (field, field_source) in relations.items():
            data = self.get_initial().get(field_name)

            if not data:
                continue

            model_class = field.Meta.model
            lookup_params = self._get_related_pk(data, model_class)

            if lookup_params:
                obj = model_class.objects.filter(**lookup_params).first()
            else:
                obj = None

            if not obj:

                raise ValidationError(
                    {field_name: f"No existing object found with `{self.lookup_field}`."})

            serializer = self._get_serializer_for_field(
                field, instance=obj, data=data)

            try:
                serializer.is_valid(raise_exception=True)
                attrs[field_source] = serializer.save()
            except ValidationError as exc:
                raise ValidationError({field_name: exc.detail})

    def update_or_create_reverse_relations(self, instance, reverse_relations):
        # print('6770')

        for field_name, (related_field, field, field_source) in reverse_relations.items():
            related_data = self.get_initial().get(field_name, None)
            if not related_data:
                continue

            instances = self._prefetch_related_instances(field, related_data)

            if related_field.many_to_many:
                getattr(instance, field_source).set(instances)
            else:
                for related_instance in instances:
                    setattr(related_instance, related_field.name, instance)
                    related_instance.save()

    def save(self, **kwargs):
        self._save_kwargs = defaultdict(dict, kwargs)

        if shall_print:
            print('6774')

        return super().save(**kwargs)

    def create(self, validated_data):
        if shall_print:
            print('6780')

        relations, reverse_relations = self._extract_relations(validated_data)

        self.update_or_create_direct_relations(validated_data, relations)

        instance = super().create(validated_data)

        self.update_or_create_reverse_relations(instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        if shall_print:
            print('6790')

        relations, reverse_relations = self._extract_relations(validated_data)

        self.update_or_create_direct_relations(validated_data, relations)

        instance = super().update(instance, validated_data)

        self.update_or_create_reverse_relations(instance, reverse_relations)

        return instance


class CustomNestedCreateMixin(CustomBaseNestedModelSerializer):
    """
    Adds nested create feature
    """

    def create(self, validated_data):
        # print('SR4488', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        ### Added code ###
        instance = self._get_existing_instance(validated_data)
        if instance:
            return self.update(instance, validated_data)
        ### End of added code ###

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance
        instance = super(CustomNestedCreateMixin, self).create(validated_data)

        self.update_or_create_reverse_relations(instance, reverse_relations)

        return instance


class CustomNestedUpdateMixin(CustomBaseNestedModelSerializer):
    shall_print = False

    default_error_messages = {
        'cannot_delete_protected': (
            "Cannot delete {instances} because "
            "protected relation exists")
    }

    def update(self, instance, validated_data):
        # print('SR5522', validated_data)

        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance
        instance = super(CustomNestedUpdateMixin, self).update(
            instance,
            validated_data,
        )
        self.update_or_create_reverse_relations(instance, reverse_relations)
        self.delete_reverse_relations_if_need(instance, reverse_relations)
        instance.refresh_from_db()
        return instance

    def perform_nested_delete_or_update(self, pks_to_delete, model_class, instance, related_field, field_source):
        if related_field.many_to_many:
            # Remove relations from m2m table
            m2m_manager = getattr(instance, field_source)
            m2m_manager.remove(*pks_to_delete)
        else:
            qs = model_class.objects.filter(pk__in=pks_to_delete)
            on_delete = related_field.remote_field.on_delete
            if on_delete in (SET_NULL, SET_DEFAULT):
                # TODO: handle on_delete.SET() ?
                if on_delete == SET_DEFAULT:
                    default = related_field.get_default()
                else:
                    default = None
                qs.update(**{related_field.name: default})
            else:
                qs.delete()

    def delete_reverse_relations_if_need(self, instance, reverse_relations):
        # Reverse `reverse_relations` for correct delete priority
        reverse_relations = OrderedDict(
            reversed(list(reverse_relations.items())))

        # Delete instances which is missed in data
        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():
            model_class = field.Meta.model

            related_data = self.get_initial()[field_name]
            # Expand to array of one item for one-to-one for uniformity
            if related_field.one_to_one:
                related_data = [related_data]

            # M2M relation can be as direct or as reverse. For direct relation
            # we should use reverse relation name
            if related_field.many_to_many:
                related_field_lookup = {
                    related_field.remote_field.name: instance,
                }
            elif isinstance(related_field, GenericRelation):
                related_field_lookup = \
                    self._get_generic_lookup(instance, related_field)
            else:
                related_field_lookup = {
                    related_field.name: instance,
                }

            current_ids = self._extract_related_pks(field, related_data)

            try:
                pks_to_delete = list(
                    model_class.objects.filter(
                        **related_field_lookup
                    ).exclude(
                        pk__in=current_ids
                    ).values_list('pk', flat=True)
                )
                self.perform_nested_delete_or_update(
                    pks_to_delete,
                    model_class,
                    instance,
                    related_field,
                    field_source
                )

            except ProtectedError as e:
                instances = e.args[1]
                self.fail('cannot_delete_protected', instances=", ".join([
                    str(instance) for instance in instances]))


class CustomWritableNestedModelSerializer(CustomNestedCreateMixin, CustomNestedUpdateMixin,
                                          serializers.ModelSerializer):
    pass


class CustomsUniqueFieldsMixin(serializers.ModelSerializer):
    """
    Fixes unique validation for nested updates when objects
    are matched by a custom lookup field (e.g. `uf`).
    """

    _unique_fields = []

    # 🔥 define which field identifies the instance
    lookup_field = 'uf'   # <-- IMPORTANT

    def get_fields(self):
        self._unique_fields = []

        fields = super().get_fields()
        for field_name, field in fields.items():
            unique_validators = [
                v for v in field.validators
                if isinstance(v, UniqueValidator)
            ]
            if unique_validators:
                self._unique_fields.append((field_name, unique_validators[0]))
                field.validators = [
                    v for v in field.validators
                    if not isinstance(v, UniqueValidator)
                ]
        return fields

    def _validate_unique_fields(self, validated_data, instance=None):
        for field_name, unique_validator in self._unique_fields:

            # 🔥 NEVER validate uniqueness of the lookup field itself
            if field_name == self.lookup_field:
                continue

            if self.partial and field_name not in validated_data:
                continue

            value = validated_data.get(field_name)
            if value is None:
                continue

            queryset = unique_validator.queryset

            # exclude current instance
            if instance is not None:
                lookup_value = getattr(instance, self.lookup_field, None)
                if lookup_value is not None:
                    queryset = queryset.exclude(**{
                        self.lookup_field: lookup_value
                    })

            if queryset.filter(**{field_name: value}).exists():
                raise ValidationError({
                    field_name: f'{field_name} must be unique.'
                })

    def create(self, validated_data):
        self._validate_unique_fields(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._validate_unique_fields(validated_data, instance=instance)
        return super().update(instance, validated_data)
