from rest_framework.routers import DefaultRouter

from logistic.views.wms_billing import WHBillingInvoiceViewSet, WHBillingPeriodViewSet
from logistic.views.wms_inbound import WHInboundViewSet
from logistic.views.wms_location import WHLocationViewSet
from logistic.views.wms_outbound import WHOutboundViewSet
from logistic.views.wms_product import WHProductViewSet
from logistic.views.wms_stock import WHStockViewSet
from logistic.views.wms_tariff import WHTariffViewSet


router = DefaultRouter()

router.register(r"inbound", WHInboundViewSet, basename="wms-inbound")
router.register(r"locations", WHLocationViewSet, basename="wms-locations")
router.register(r"outbound", WHOutboundViewSet, basename="wms-outbound")
router.register(r"products", WHProductViewSet, basename="wms-products")
router.register(r"stock", WHStockViewSet, basename="wms-stock")
router.register(r"tariffs", WHTariffViewSet, basename="wms-tariffs")
router.register(r"billing-periods", WHBillingPeriodViewSet, basename="wms-billing-periods")
router.register(r"billing-invoices", WHBillingInvoiceViewSet, basename="wms-billing-invoices")


urlpatterns = router.urls
