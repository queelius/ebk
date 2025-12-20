"""
Views DSL for ebk.

A composable, non-destructive system for defining curated subsets of a library
with optional metadata overrides. Following SICP principles:

- Primitives: all, none, filter, ids, view references
- Combination: union, intersect, difference
- Abstraction: named views become new primitives
- Closure: combining views yields a view

Example:
    from ebk.views import ViewEvaluator

    evaluator = ViewEvaluator(session)

    # Evaluate a view definition
    books = evaluator.evaluate({
        'select': {
            'intersect': [
                {'filter': {'subject': 'programming'}},
                {'filter': {'favorite': True}}
            ]
        },
        'order': {'by': 'title'}
    })
"""

from .dsl import ViewEvaluator, TransformedBook
from .service import ViewService

__all__ = ['ViewEvaluator', 'TransformedBook', 'ViewService']
