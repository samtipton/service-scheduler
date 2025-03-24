from decimal import Decimal
import functools


def round_decimal(places: int = 4) -> Decimal:
    """Round the result of a function to 4 decimal places"""

    def decorator_round_decimal(func):
        @functools.wraps(func)
        def wrapper_round_decimal(*args, **kwargs):
            result = func(*args, **kwargs)
            return Decimal(round(result, places))

        return wrapper_round_decimal

    return decorator_round_decimal


def decimal(func) -> Decimal:
    """Round the result of a function to 4 decimal places"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            return Decimal(result)
        except (TypeError, ValueError):
            return result

    return wrapper
