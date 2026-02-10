from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, json, tempfile
from datetime import datetime
from pathlib import Path


EXECUTION_MODE = os.getenv("EXECUTION_MODE", "dry-run").lower()
EXECUTIONS_DIR = os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions")

EXECUTABLE_TYPES = {
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
}

def handle_region(obj, client, apply):
    name = obj["name"]

    if not hasattr(client, "get_region"):
        return "PLANNED", "Region handler not implemented yet"

    exists = client.get_region(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create region"

    client.add_region(name)
    return "CREATED", "Region created"


def handle_location(obj, client, apply):
    name = obj["name"]

    if not hasattr(client, "get_location"):
        return "PLANNED", "Location handler not implemented yet"

    exists = client.get_location(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create location"

    client.add_location(name)
    return "CREATED", "Location created"


def handle_physicallocation(obj, client, apply):
    name = obj["name"]
    desc = obj.get("inputs", {}).get("description")

    if not hasattr(client, "get_physicallocation"):
        return "PLANNED", "Physical location handler not implemented yet"

    exists = client.get_physicallocation(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create physical location"

    client.add_physicallocation(name, description=desc)
    return "CREATED", "Physical location created"


def handle_srst(obj, client, apply):
    name = obj["name"]
    ip = obj.get("inputs", {}).get("ip")

    if not hasattr(client, "get_srst"):
        return "PLANNED", "SRST handler not implemented yet"

    exists = client.get_srst(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create SRST reference"

    client.add_srst(name, ipAddress=ip)
    return "CREATED", "SRST reference created"


def handle_partition(obj: dict, client, apply: bool):
    name = obj["name"]
    desc = obj.get("description")

    exists = client.get_partition(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create partition"

    client.add_partition(name, description=desc)
    return "CREATED", "Partition created"


def handle_css(obj: dict, client, apply: bool):
    name = obj["name"]
    desc = obj.get("description")
    members = obj.get("inputs", {}).get("members_partitions") or []

    exists = client.get_css(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", f"Would create CSS with {len(members)} members"

    client.add_css(name, description=desc, members=members)
    return "CREATED", "CSS created"


def handle_mrg(obj, client, apply):
    name = obj["name"]
    desc = obj.get("description")
    members = obj.get("inputs", {}).get("members") or []
    
    if not hasattr(client, "get_mediaresourcegroup"):
        return "PLANNED", "MRG handler not implemented yet"

    exists = client.get_mediaresourcegroup(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create MRG"

    client.add_mediaresourcegroup(name, description=desc, members=members)
    return "CREATED", "MRG created"


def handle_mrgl(obj, client, apply):
    name = obj["name"]
    members = obj.get("inputs", {}).get("members") or []

    if not hasattr(client, "get_mediaresourcelist"):
        return "PLANNED", "MRGL handler not implemented yet"

    exists = client.get_mediaresourcelist(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create MRGL"

    client.add_mediaresourcelist(name, members=members)
    return "CREATED", "MRGL created"


def handle_devicepool(obj, client, apply):
    name = obj["name"]
    inp = obj.get("inputs", {})

    if not hasattr(client, "get_devicepool"):
        return "PLANNED", "Device Pool handler not implemented yet"

    exists = client.get_devicepool(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create device pool"

    client.add_devicepool(
        name=obj["name"],
        datetimeSettingName=inp["date_time_group"],
        callManagerGroupName=inp["ucm_group"],
        MediaResourceListName=inp["mrgl"],
        regionName=inp["region"],
        locationName=inp["location"],
        srstName=inp.get("srst_reference"),
        physicalLocationName=inp.get("physical_location"),
        deviceMobilityGroupName=inp.get("device_mobility_group"),
    )
    return "CREATED", "Device Pool created"

    # # Device Pools require MANY attributes — do not guess
    # raise RuntimeError(
    #     "Device Pool creation requires region, location, SRST, MRGL, "
    #     "date/time group, etc. Not safe to auto-create yet."
    # )


def handle_dmi(obj, client, apply):
    name = obj["name"]
    subnet = obj.get("inputs", {}).get("subnet")
    mask = obj.get("inputs", {}).get("mask")
    members = obj.get("inputs", {}).get("members") or []

    if not hasattr(client, "get_devicemobility"):
        return "PLANNED", "Device Mobility handler not implemented yet"

    exists = client.get_devicemobility(name)
    if exists:
        return "EXISTS", None

    if not apply:
        return "PLANNED", "Would create Device Mobility"


    client.add_devicemobility(name, subnet=subnet, mask=mask, members=members)
    return "CREATED", "Device Mobility created"


HANDLERS = {
    "partition": handle_partition,
    "css": handle_css,
    "region": handle_region,
    "location": handle_location,
    "physical_location": handle_physicallocation,
    "srst": handle_srst,
    "mrg": handle_mrg,
    "mrgl": handle_mrgl,
    "device_pool": handle_devicepool,
    "device_mobility": handle_dmi,
}

ROLLBACK_MAP = {
    "region": {
        "method": "removeRegion",
        "args": lambda o: {"name": o["name"]},
    },
    "location": {
        "method": "removeLocation",
        "args": lambda o: {"name": o["name"]},
    },
    "physical_location": {
        "method": "removePhysicalLocation",
        "args": lambda o: {"name": o["name"]},
    },
    "srst": {
        "method": "removeSrst",
        "args": lambda o: {"name": o["name"]},
    },
    "partition": {
        "method": "removeRoutePartition",
        "args": lambda o: {"name": o["name"]},
    },
    "css": {
        "method": "removeCss",
        "args": lambda o: {"name": o["name"]},
    },
    "mrg": {
        "method": "removeMediaResourceGroup",
        "args": lambda o: {"name": o["name"]},
    },
    "mrgl": {
        "method": "removeMediaResourceList",
        "args": lambda o: {"name": o["name"]},
    },
    "device_pool": {
        "method": "removeDevicePool",
        "args": lambda o: {"name": o["name"]},
    },
    "device_mobility": {
        "method": "removeDeviceMobility",
        "args": lambda o: {"name": o["name"]},
    },
}

def count_total_steps(plan: dict) -> int:
    count = 0
    for site in plan.get("sites", []):
        for obj in site.get("objects", []):
            if obj["action"] == "create" and obj["type"] in EXECUTABLE_TYPES:
                count += 1
    return count

def write_execution(execution: dict):
    Path(EXECUTIONS_DIR).mkdir(parents=True, exist_ok=True)
    path = Path(EXECUTIONS_DIR) / f"{execution['plan_id']}.json"
    with open(path, "w") as f:
        json.dump(execution, f, indent=2)

def execute_plan(plan: dict, client, apply: bool = False) -> dict:
    plan_id = plan["plan_id"]

    total_objects = count_total_steps(plan)

    execution = {
        "plan_id": plan_id,
        "env_name": plan.get("env_name"),
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "status": "IN_PROGRESS",
        "total_steps": total_objects,
        "completed_steps": 0,
        "current_step": None,
        "results": []
    }

    write_execution(execution)

    results = []

    for site in plan.get("sites", []):
        site_code = site["site_code"]

        for obj in site.get("objects", []):

            # Skip non-create or non-executable objects (don’t count toward progress)
            if obj["action"] != "create" or obj["type"] not in EXECUTABLE_TYPES:
                result = {
                    "site_code": site_code,
                    "type": obj["type"],
                    "name": obj["name"],
                    "action": obj["action"],
                    "status": "SKIPPED",
                    "message": "Not executable",
                    "timestamp": datetime.utcnow().isoformat()
                }
                execution["results"].append(result)
                continue

            # 🔹 Update CURRENT STEP
            execution["current_step"] = {
                "site_code": site_code,
                "type": obj["type"],
                "name": obj["name"]
            }
            write_execution(execution)

            result = {
                "site_code": site_code,
                "type": obj["type"],
                "name": obj["name"],
                "action": obj["action"],
                "timestamp": datetime.utcnow().isoformat()
            }

            handler = HANDLERS.get(obj["type"])

            if handler is None:
                result["status"] = "PLANNED"
                result["message"] = "No handler registered"
                execution["results"].append(result)
                continue

            try:
                status, message = handler(obj, client, apply)
                result["status"] = status
                if message:
                    result["message"] = message

                if status == "CREATED":
                    rb = ROLLBACK_MAP.get(obj["type"])
                    if rb:
                        result["rollback"] = {
                            "action": "delete",
                            "method": rb["method"],
                            "args": rb["args"](obj),
                        }

            except Exception as e:
                result["status"] = "FAILED"
                result["message"] = str(e)

            execution["results"].append(result)
            results.append(result)

            # 🔹 UPDATE PROGRESS
            execution["completed_steps"] += 1
            write_execution(execution)

            # Optional: stop immediately on failure
            # if result["status"] == "FAILED":
            #     execution["status"] = "FAILED"
            #     break

    # ===== FINALIZE EXECUTION =====

    execution["finished_at"] = datetime.utcnow().isoformat()
    execution["current_step"] = None

    created = any(r["status"] == "CREATED" for r in execution["results"])
    failed = any(r["status"] == "FAILED" for r in execution["results"])

    if failed and created:
        execution["status"] = "PARTIAL_SUCCESS"
    elif failed:
        execution["status"] = "FAILED"
    else:
        execution["status"] = "SUCCESS"

    write_execution(execution)

    return {
        "status": execution["status"],
        "results": results
    }
    
def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def rollback_plan(plan_id: str, client, apply: bool = False) -> dict:
    exec_dir = Path(os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions"))
    exec_path = exec_dir / f"{plan_id}.json"

    if not exec_path.exists():
        return {"status": "ERROR", "message": f"Execution file not found: {exec_path}"}

    execution = json.loads(exec_path.read_text())
    steps = execution.get("results", [])

    rollback_steps = [s for s in steps if s.get("status") == "CREATED" and s.get("rollback")]
    rollback_steps.reverse()

    rb_path = exec_dir / f"{plan_id}.rollback.json"
    total_steps = len(rollback_steps)

    out = {
        "plan_id": plan_id,
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "apply": apply,
        "status": "IN_PROGRESS",
        "total_steps": total_steps,
        "completed_steps": 0,
        "current_step": None,
        "results": []
    }

    # write initial status immediately so polling sees it
    rb_path.write_text(json.dumps(out, indent=2))

    for idx, s in enumerate(rollback_steps, start=1):
        rb = s["rollback"]
        method = rb.get("method")
        args = rb.get("args", {}) or {}

        out["current_step"] = {
            "type": s.get("type"),
            "name": s.get("name"),
            "site_code": s.get("site_code"),
            "order": idx
        }

        item = {
            "site_code": s.get("site_code"),
            "type": s.get("type"),
            "name": s.get("name"),
            "timestamp": datetime.utcnow().isoformat(),
            "rollback": rb,
        }

        try:
            if not apply:
                item["status"] = "PLANNED"
                item["message"] = f"Would call {method}({args})"
            else:
                fn = getattr(client, method, None)
                if not fn:
                    fn = lambda **kw: client.remove_op(method, **kw)

                fn(**args)
                item["status"] = "ROLLED_BACK"
                item["message"] = f"{method} succeeded"

        except Exception as e:
            item["status"] = "FAILED"
            item["message"] = str(e)

        out["results"].append(item)
        out["completed_steps"] = idx

        # persist progress after each step
        rb_path.write_text(json.dumps(out, indent=2))

    out["finished_at"] = datetime.utcnow().isoformat()
    failed = any(r["status"] == "FAILED" for r in out["results"])
    out["status"] = "FAILED" if failed else "SUCCESS"
    out["current_step"] = None

    rb_path.write_text(json.dumps(out, indent=2))
    return out