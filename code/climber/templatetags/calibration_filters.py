"""
Template filters for calibration functionality
"""

from django import template

register = template.Library()


@register.filter
def js_array(value):
    """Format a Python list as a JavaScript array"""
    if not value:
        return '[]'
    
    # Handle nested arrays (like 2D matrices)
    if isinstance(value[0], (list, tuple)):
        # It's a 2D array/matrix
        rows = []
        for row in value:
            if isinstance(row, (list, tuple)):
                rows.append('[' + ','.join(str(x) for x in row) + ']')
            else:
                rows.append('[' + str(row) + ']')
        return '[' + ','.join(rows) + ']'
    else:
        # It's a 1D array
        return '[' + ','.join(str(x) for x in value) + ']'