from django.core.exceptions import ValidationError


class ProtectedDeleteMixin:
    '''
        The reverse-relation check works for ManyToMany, but the mixin I gave works for both ManyToMany and ForeignKey

    '''
    protected_related = []  # list of related_name strings

    def delete(self, *args, **kwargs):
        for rel in self.protected_related:
            related_manager = getattr(self, rel)
            if related_manager.exists():
                raise ValidationError(
                    f"Cannot delete {self.__class__.__name__} '{self}' "
                    f"because it is used in {rel.replace('_', ' ')}."
                )
        super().delete(*args, **kwargs)
