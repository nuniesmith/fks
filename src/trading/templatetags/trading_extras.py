"""
Custom template tags for trading app
"""
from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary by key.
    Usage: {{ my_dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter(name='abs')
def abs_filter(value):
    """
    Template filter to get absolute value.
    Usage: {{ value|abs }}
    """
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value
