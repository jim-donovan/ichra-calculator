"""
Services for Contribution Evaluation module.

These services encapsulate business logic and external integrations,
keeping components focused on presentation.
"""

from .strategy_service import StrategyService
from .recommendation_service import RecommendationService
from .subsidy_service import SubsidyService
from .ai_client import (
    get_ai_client,
    is_ai_available,
    generate_ai_recommendation,
)

__all__ = [
    'StrategyService',
    'RecommendationService',
    'SubsidyService',
    'get_ai_client',
    'is_ai_available',
    'generate_ai_recommendation',
]
