from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from abb.views import robots_txt, CountryList, CurrencyList

urlpatterns = [

    path('', robots_txt, name='robots-txt-root'),
    path('robots.txt/', robots_txt, name='robots-txt-api'),

    # path('gen-data/', gen_data, name='gen-data'),

    # path('body-types/', BodyTypeList.as_view(), name='bodytypes'),

    path('countries/', CountryList.as_view(), name='countries'),

    path('currencies/', CurrencyList.as_view(), name='currencies'),

    # path('incoterms/', IncotermTypeList.as_view(), name='incoterms'),

    # path('modes/', MtypeList.as_view(), name='modes'),

    # path('statuses/', StypeList.as_view(), name='statuses'),

]

urlpatterns = format_suffix_patterns(urlpatterns)
