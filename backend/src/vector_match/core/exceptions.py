class DomainError(Exception):
    """业务异常基类。"""


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class ProviderConfigError(DomainError):
    pass
