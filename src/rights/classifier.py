"""Rights and licensing classification for videos."""

import logging
from dataclasses import dataclass
from enum import Enum

from src.youtube.models import YouTubeVideo

logger = logging.getLogger(__name__)


class RightsStatus(str, Enum):
    """Possible rights status values."""

    UNKNOWN = "UNKNOWN"
    STANDARD_YOUTUBE_LICENSE = "STANDARD_YOUTUBE_LICENSE"
    CREATIVE_COMMONS = "CREATIVE_COMMONS"
    USER_AUTHORIZED = "USER_AUTHORIZED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"


@dataclass
class RightsInfo:
    """Structured rights information for a video."""

    license_type: str
    rights_status: RightsStatus
    rights_notes: str
    rights_verified: bool
    requires_review: bool


class RightsClassifier:
    """Classifies video rights based on available metadata."""

    CC_WARNING = (
        "Creative Commons detected. Independent verification of the specific "
        "CC license terms is required before reuse. The uploader's claimed license "
        "should be verified on the video page."
    )

    STANDARD_WARNING = (
        "Standard YouTube License. This typically means the content is copyrighted "
        "by the uploader or a third party. Reuse requires explicit permission."
    )

    UNKNOWN_WARNING = (
        "Rights status could not be determined. Assume all rights are reserved. "
        "Do not reproduce or publish without obtaining proper permissions."
    )

    @classmethod
    def classify(cls, video: YouTubeVideo) -> RightsInfo:
        """Classify rights for a video based on API metadata."""
        license_type = (video.license_type or "UNKNOWN").lower()

        if license_type == "creativecommon":
            return RightsInfo(
                license_type="Creative Commons",
                rights_status=RightsStatus.CREATIVE_COMMONS,
                rights_notes=cls.CC_WARNING,
                rights_verified=False,
                requires_review=True,
            )

        if license_type == "youtube":
            return RightsInfo(
                license_type="Standard YouTube License",
                rights_status=RightsStatus.STANDARD_YOUTUBE_LICENSE,
                rights_notes=cls.STANDARD_WARNING,
                rights_verified=False,
                requires_review=True,
            )

        return RightsInfo(
            license_type="UNKNOWN",
            rights_status=RightsStatus.UNKNOWN,
            rights_notes=cls.UNKNOWN_WARNING,
            rights_verified=False,
            requires_review=True,
        )

    @classmethod
    def apply_to_video(cls, video: YouTubeVideo) -> None:
        """Apply rights classification directly to a video model."""
        info = cls.classify(video)
        video.license_type = info.license_type
        video.rights_status = info.rights_status.value
        video.rights_notes = info.rights_notes
        video.rights_verified = info.rights_verified
