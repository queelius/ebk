"""
Network analysis integration for EBK.

This integration provides graph/network analysis capabilities including:
- Co-author networks
- Subject co-occurrence graphs  
- Citation networks
- Network metrics and statistics

Installation:
    pip install ebk[network]  # For basic functionality
    pip install ebk[network-advanced]  # Includes NetworkX for advanced metrics
"""

from .network_analyzer import NetworkAnalyzer

# Optional: Import NetworkX version if available
try:
    from .network_analyzer import NetworkXAnalyzer
    __all__ = ['NetworkAnalyzer', 'NetworkXAnalyzer']
except ImportError:
    __all__ = ['NetworkAnalyzer']