import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from avv.models import IssueDocument

from bch.serializers import IssueDocumentWSSerializer
from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class IssueDocumentMixin:
    @action(detail=False)
    async def subscribe_issue_document(self, **kwargs):
        logger.info(f'WS Subscribed to IssueDocument changes.')
        company = await get_user_company_async(self.scope["user"])
        await self.issue_document_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(IssueDocument)
    async def issue_document_change(self, message, **kwargs):
        await self.send_json({
            "type": "issue_document",
            **message
        })

    @issue_document_change.serializer
    def issue_document_serializer(self, instance, action, **kwargs):
        return {
            "action": action.value,
            "data": IssueDocumentWSSerializer(instance).data,
        }
