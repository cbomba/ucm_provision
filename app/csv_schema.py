from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

def split_csv_list(value: str | None) -> List[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]

class SiteRow(BaseModel):
    # identity (required)
    site_code: str = Field(min_length=1)
    site_detail: str = Field(min_length=1)  # "Elmhurst, IL"
    state: str = Field(min_length=2, max_length=2)
    city: str = Field(min_length=1)

    # region (optional in Phase 1 plan, but included if present)
    region_audio_codec_preference_list: Optional[str] = None
    region_max_audio_bitrate: Optional[str] = None
    region_max_video_bitrate: Optional[str] = None
    region_max_immersive_bitrate: Optional[str] = None

    # location bw (optional)
    location_audio_bw: Optional[str] = None     # "Unlimited" or "64"
    location_video_bw: Optional[str] = None     # "None" / "Unlimited" / kbps
    location_immersive_bw: Optional[str] = None

    # physical location
    physical_location_description: Optional[str] = None

    # SRST
    srst_ip: Optional[str] = None

    # media
    mrg_members: Optional[str] = None           # comma list
    mrgl_members: Optional[str] = None          # comma list, can use "SITE_MRG"

    # device pool references (these should usually be required per customer)
    ucm_group: Optional[str] = None
    date_time_group: Optional[str] = None
    softkey_template: Optional[str] = None
    device_mobility_group: Optional[str] = None

    # device mobility info
    mobility_subnet: Optional[str] = None
    mobility_mask: Optional[str] = None


    @field_validator("site_code")
    @classmethod
    def uppercase_site_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("state")
    @classmethod
    def uppercase_state(cls, v: str) -> str:
        return v.strip().upper()

    def mrg_members_list(self) -> List[str]:
        return split_csv_list(self.mrg_members)

    def mrgl_members_list(self) -> List[str]:
        return split_csv_list(self.mrgl_members)

    def srst_enabled_bool(self) -> bool:
        return bool(self.srst_ip)
    
    def device_mobility_enabled_bool(self) -> bool:
        return bool(self.mobility_subnet and self.mobility_mask)