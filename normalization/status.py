"""Decide how trustworthy a record's usage is.

Phase 4 rule 5 asks that reported and estimated usage stay distinguishable. Nothing in
the OpenCode path estimates today, but the distinction is recorded now so a future
provider that derives a count has a place to say so, rather than passing an estimate off
as something the provider reported.
"""

import logging

from normalization.totals import TokenCategories
from schemas.usage import UsageStatus

logger = logging.getLogger(__name__)


def resolve_usage_status(categories: TokenCategories, estimated: bool = False) -> UsageStatus:
    """Classify a record as reported, estimated, or unavailable.

    `estimated` is set by a collector that derived a count the provider did not give.
    A record with no counts at all is unavailable even when marked estimated, because
    there is nothing to be estimated from.
    """
    if not categories.has_any_value:
        return "unavailable"
    if estimated:
        logger.debug("record carries an estimated token count")
        return "estimated"
    return "reported"
