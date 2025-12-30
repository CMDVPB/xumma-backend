from rest_framework.exceptions import APIException


class CustomApiException(APIException):
    """ Docstring """

    def __init__(self, status, detail):
        """ Docstring """
        self.status_code = status
        self.detail = detail
