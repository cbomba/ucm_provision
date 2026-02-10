from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid
import os
from app import naming
from app.naming import NamingProfile
from app.csv_schema import SiteRow

OBJECT_ORDER = [
    "region",
    "location",
    "physical_location",
    "srst",
    "partition",
    "css",
    "mrg",
    "mrgl",
    "device_pool",
    "device_mobility",
]

FINAL_OBJECT_ORDER = [
    "region",
    "location",
    "physical_location",
    "srst",
    "partition",
    "css",
    "mrg",
    "mrgl",
    "device_pool",
    "device_mobility",
]

BACKOUT_ORDER = [
  "device_mobility",
  "device_pool",
  "mrgl",
  "mrg",
  "css",
  "partition",
  "srst",
  "physical_location",
  "location",
  "region",
]

FRIENDLY = {
    "region": "Region",
    "location": "Location",
    "physical_location": "Physical Location",
    "srst": "SRST",
    "partition": "Partition",
    "css": "Calling Search Space",
    "mrg": "Media Resource Group",
    "mrgl": "Media Resource Group List",
    "device_pool": "Device Pool",
    "device_mobility": "Device Mobility"
}

def _ctx(org: str, row: SiteRow) -> dict:
    return {
        "org": org,
        "state": row.state,
        "site_code": row.site_code,
        "site_detail": row.site_detail,
        "city": row.city,
    }


def build_dialplan_objects(
    row: SiteRow,
    org: str,
    dialplan: dict,
    exists_lookup: Optional[callable] = None,
) -> List[dict]:
    ctx = {
        "site": row.site_code,
        "site_code": row.site_code,
        "site_name": row.site_detail,
        "city": row.city,
        "state": row.state,
        "org": org,
    }

    objects: List[dict] = []

    globals_partitions = (dialplan.get("globals") or {}).get("partitions", {})

    # -----------------------
    # Partitions (site scope)
    # -----------------------
    partition_name_map: dict[str, str] = {}

    for key, p in (dialplan.get("partitions") or {}).items():
        if p.get("scope") != "site":
            continue

        name_tmpl = p["name"]
        desc_tmpl = p.get("description", "")

        part_name = name_tmpl.format(**ctx)
        part_desc = desc_tmpl.format(**ctx)

        partition_name_map[key] = part_name

        action = "create"
        if exists_lookup and exists_lookup("partition", part_name):
            action = "skip"

        objects.append({
            "type": "partition",
            "friendly": FRIENDLY["partition"],
            "name": part_name,
            "description": part_desc,
            "action": action,
            "depends_on": [],
            "inputs": {},
        })

    # -----------------------
    # CSS (site scope)
    # -----------------------
    for key, c in (dialplan.get("css") or {}).items():
        name_tmpl = c["name"]
        desc_tmpl = c.get("description", "")

        css_name = name_tmpl.format(**ctx)
        css_desc = desc_tmpl.format(**ctx)

        members: List[str] = []

        for m in c.get("members", []):
            if m in partition_name_map:
                members.append(partition_name_map[m])
            elif m in globals_partitions:
                members.append(globals_partitions[m])
            else:
                raise ValueError(
                    f"CSS '{key}' references unknown partition '{m}' "
                    f"for site {row.site_code}"
                )

        action = "create"
        if exists_lookup and exists_lookup("css", css_name):
            action = "skip"

        objects.append({
            "type": "css",
            "friendly": FRIENDLY["css"],
            "name": css_name,
            "description": css_desc,
            "action": action,
            "depends_on": ["partition"],
            "inputs": {
                "members_partitions": members
            },
        })

    return objects

@dataclass
class PlanResult:
    plan_id: str
    plan: dict
    errors: List[str]
    warnings: List[str]

def build_plan(
    rows: List[SiteRow],
    naming: NamingProfile,
    org: str,
    env_name: str,
    exists_lookup: Optional[callable] = None,  # fn(obj_type, name) -> bool
) -> PlanResult:
    """
    exists_lookup is optional now; later it will call CUCM AXL getXxx to decide create/skip/update.
    """
    plan_id = str(uuid.uuid4())
    dialplan = getattr(naming, "dialplan", None)
    errors: List[str] = []
    warnings: List[str] = []

    sites_out: List[dict] = []

    seen_site_codes = set()
    for i, row in enumerate(rows, start=2):  # assume header line is 1
        if row.site_code in seen_site_codes:
            errors.append(f"Duplicate site_code '{row.site_code}' (CSV row {i})")
            continue
        seen_site_codes.add(row.site_code)

        ctx = _ctx(org, row)

        # compute names
        names = {t: naming.render_name(t, ctx) for t in FRIENDLY.keys()}
        descs = {t: naming.render_description(t, ctx) for t in FRIENDLY.keys()}

        # MRGL member keyword handling
        mrg_name = names["mrg"]
        mrgl_members = row.mrgl_members_list()
        mrgl_members_resolved: List[str] = []
        for m in mrgl_members:
            if m == "SITE_MRG":
                mrgl_members_resolved.append(mrg_name)
            else:
                mrgl_members_resolved.append(m)

        # SRST requirement check if enabled
        srst_enabled = bool(getattr(row, "srst_ip", None))

        # Device Mobility requirement check
        dm_enabled = bool(getattr(row, "mobility_subnet", None)) and bool(getattr(row, "mobility_mask", None))

        # Build object list
        dialplan_objects: list[dict] = []
        infra_objects: list[dict] = []

        # 1) Dialplan-driven objects first
        if naming.dialplan:
            dialplan_objects.extend(
                build_dialplan_objects(
                    row=row,
                    org=org,
                    dialplan=naming.dialplan,
                    exists_lookup=exists_lookup,
                )
            )

        # 2) Infra objects (skip partition/css here when dialplan present)
        for obj_type in OBJECT_ORDER:
            if obj_type == "srst" and not srst_enabled:
                continue
            if obj_type == "device_mobility" and not dm_enabled:
                continue
            if dialplan and obj_type in ("partition", "css"):
                continue

            obj_name = names[obj_type]
            action = "create"
            exists = False
            if exists_lookup:
                try:
                    exists = bool(exists_lookup(obj_type, obj_name))
                except Exception as e:
                    warnings.append(f"{row.site_code}: exists check failed for {obj_type} '{obj_name}': {e}")
                    exists = False

            if exists:
                action = "skip"

            obj = {
                "type": obj_type,
                "friendly": FRIENDLY[obj_type],
                "name": obj_name,
                "description": descs[obj_type],
                "action": action,
                "depends_on": [],
                "inputs": {},
            }

            if obj_type == "region":
                obj["inputs"] = {
                    "audio_codec_preference_list": row.region_audio_codec_preference_list,
                    "max_audio_bitrate": row.region_max_audio_bitrate,
                    "max_video_bitrate": row.region_max_video_bitrate,
                    "max_immersive_bitrate": row.region_max_immersive_bitrate,
                }
            elif obj_type == "location":
                obj["inputs"] = {
                    "hub_relationship": "Hub_None",
                    "audio_bw": row.location_audio_bw,
                    "video_bw": row.location_video_bw,
                    "immersive_bw": row.location_immersive_bw,
                }
            elif obj_type == "physical_location":
                obj["inputs"] = {"description": row.physical_location_description}
            elif obj_type == "srst":
                obj["inputs"] = {"ip": row.srst_ip}
            elif obj_type == "mrg":
                members = row.mrg_members_list()
                if not members:
                    continue
                obj["inputs"] = {"members": members}
            elif obj_type == "mrgl":
                obj["inputs"] = {"members": mrgl_members_resolved}
            elif obj_type == "device_pool":
                obj["inputs"] = {
                    "ucm_group": row.ucm_group,
                    "date_time_group": row.date_time_group,
                    "region": names["region"],
                    "location": names["location"],
                    "physical_location": names["physical_location"],
                    "srst_reference": names["srst"] if srst_enabled else None,
                    "mrgl": names["mrgl"],
                    "device_mobility_group": row.device_mobility_group,
                }
            elif obj_type == "device_mobility":
                obj["inputs"] = {
                    "subnet": row.mobility_subnet,
                    "mask": row.mobility_mask,
                    "members": [names["device_pool"]],
                }

            infra_objects.append(obj)

        # 3) Merge + enforce FINAL_OBJECT_ORDER (THIS MUST BE AFTER infra_objects is built)
        objects_by_type: dict[str, list[dict]] = {}
        for o in (dialplan_objects + infra_objects):
            objects_by_type.setdefault(o["type"], []).append(o)

        objects: list[dict] = []
        for t in FINAL_OBJECT_ORDER:
            objects.extend(objects_by_type.get(t, []))

        # Fill dependencies
        by_type = {o["type"]: o for o in objects}
        for o in objects:
            t = o["type"]
            deps: List[str] = []
            if t == "location":
                deps = ["region"]
            elif t == "css":
                deps = ["partition"]
            elif t == "mrgl":
                deps = []
            elif t == "device_pool":
                deps = ["region", "location", "physical_location", "mrgl"]
                if srst_enabled:
                    deps.insert(3, "srst")

                # Only require these if they exist in this site's object set
                site_types = {x["type"] for x in objects}
                if "partition" in site_types:
                    deps.append("partition")
                if "css" in site_types:
                    deps.append("css")
            elif t == "device_mobility":
                deps = ["device_pool"]
            o["depends_on"] = deps

        sites_out.append({
            "site_code": row.site_code,
            "site_detail": row.site_detail,
            "objects": objects,
        })

    plan = {
        "plan_id": plan_id,
        "env_name": env_name,
        "org": org,
        "site_count": len(sites_out),
        "sites": sites_out,
        "summary": summarize_plan(sites_out),
    }

    return PlanResult(plan_id=plan_id, plan=plan, errors=errors, warnings=warnings)

def summarize_plan(sites: List[dict]) -> dict:
    counts: Dict[str, Dict[str, int]] = {}
    for s in sites:
        for o in s["objects"]:
            t = o["type"]
            a = o["action"]
            counts.setdefault(t, {"create": 0, "skip": 0, "update": 0})
            if a not in counts[t]:
                counts[t][a] = 0
            counts[t][a] += 1
    return counts