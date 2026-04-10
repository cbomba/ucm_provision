from __future__ import annotations
import csv
import io
import json
import os
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse
import yaml


from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from wxcadm import Webex

from app.db import init_db, db_connect
from app.csv_schema import SiteRow
from app.naming import NamingProfile
from app.planner import build_plan
from app.secrets import encrypt_json, decrypt_json
from app.executor import execute_plan, rollback_plan
from app.integrations.ucm_axl import UcmAxlClient
from app.integrations.webex import WebexClient


app = FastAPI(title="CUCM Site Provisioner", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
def on_startup():
    init_db()
    Path(os.getenv("APP_DATA_DIR", "/data")).mkdir(parents=True, exist_ok=True)
    Path(os.getenv("APP_DATA_EXECUTIONS_DIR","/app/data/executions")).mkdir(parents=True, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
def index():
    return Path("app/static/index.html").read_text(encoding="utf-8")


class EnvUpsert(BaseModel):
    name: str
    platform: str = "CUCM"
    
    #CUCM
    cucm_url: Optional[str] = None
    cucm_username: Optional[str] = None
    cucm_password: Optional[str] = None
    cucm_verify_tls: bool = False
    
    #Webex
    access_token: Optional[str] = None
    org_id: Optional[str] = None

class EnvListItem(BaseModel):
    name: str
    platform: str
    
class VerifyGlobalsRequest(BaseModel):
    passphrase: str

def resolve_dialplan_path(env_name: str) -> str:
    base = Path(os.getenv("APP_DATA_DIR", "/data")) / "dialplans" / "customers"
    safe_env = env_name.lower().replace(" ", "-")
    path = base / safe_env / "dialplan.yml"

    print("DEBUG: Dialplan base =", base)
    print("DEBUG: Dialplan env dir =", base / safe_env)
    print("DEBUG: Dialplan full path =", path)
    print("DEBUG: Exists? =", path.exists())

    return str(path)

def resolve_naming_path(env_name: str) -> str:
    base = Path(os.getenv("APP_DATA_DIR", "/data")) / "dialplans" / "customers"
    safe_env = env_name.lower().replace(" ", "-")
    path = base / safe_env / "naming.yml"

    print("DEBUG: Naming base =", base)
    print("DEBUG: Naming env dir =", base / safe_env)
    print("DEBUG: Naming full path =", path)
    print("DEBUG: Exists? =", path.exists())

    return str(path)

def ensure_env_files(env_name: str):
    base = Path(os.getenv("APP_DATA_DIR", "/data")) / "dialplans" / "customers"

    safe_env = env_name.lower().replace(" ", "-")
    env_dir = base / safe_env
    env_dir.mkdir(parents=True, exist_ok=True)

    demo_dir = base / "Demo"

    files_to_copy = [
        "dialplan.yml",
        "naming.yml",
    ]

    for fname in files_to_copy:
        template = demo_dir / fname
        target = env_dir / fname

        if not template.exists():
            print(f"WARNING: Demo template not found: {template}")
            continue

        if not target.exists():
            shutil.copy(template, target)
            print(f"Created {fname} for environment '{env_name}' from Demo template")
        
        
def normalize_cucm_url(url: str) -> str:
    url = url.strip()

    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)

    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path  # handles cases like "10.1.1.1"
    path = parsed.path or ""

    # Ensure port
    if ":" not in netloc:
        netloc = f"{netloc}:8443"

    # Normalize path
    if not path or path == "/":
        path = "/axl/"
    else:
        if not path.endswith("/"):
            path += "/"
        if not path.lower().startswith("/axl"):
            path = "/axl/"

    return urlunparse((scheme, netloc, path, "", "", ""))

def build_client(env: Dict[str, Any]):
    platform = env.get("platform", "CUCM").upper()

    if platform == "CUCM":
        return UcmAxlClient(
            base_url=env["cucm_url"],
            username=env["cucm_username"],
            password=env["cucm_password"],
            verify_tls=env.get("cucm_verify_tls", False),
        )

    if platform == "WEBEX":
        return WebexClient(
            access_token=env["access_token"]
        )

    raise ValueError(f"Unsupported platform: {platform}")

@app.get("/api/envs", response_model=List[EnvListItem])
def list_envs():
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, platform, org_id FROM envs ORDER BY name")
        return [{"name": r[0], "platform": r[1], "org_id": r[2]} for r in cur.fetchall()]
    finally:
        conn.close()

@app.post("/api/envs")
def upsert_env(payload: EnvUpsert, passphrase: Optional[str] = None):
    passphrase = passphrase or os.getenv("APP_PASSPHRASE")
    if not passphrase:
        raise HTTPException(status_code=400, detail="passphrase is required (query param passphrase or APP_PASSPHRASE)")

    data = payload.model_dump()
    platform = data.get("platform", "CUCM").upper()

    if platform == "CUCM":
        if not data.get("cucm_url") or not data.get("cucm_username") or not data.get("cucm_password"):
            raise HTTPException(status_code=400, detail="Missing CUCM credentials")
        
        data["cucm_url"] = normalize_cucm_url(data["cucm_url"])

    elif platform == "WEBEX":
        if not data.get("access_token"):
            raise HTTPException(status_code=400, detail="Missing Webex access token")
        
        if not data.get("org_id"):
            raise HTTPException(status_code=400, detail="Missing Webex Org ID")

    blob = encrypt_json(passphrase, data)
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO envs(name, payload_encrypted, platform, org_id, created_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET payload_encrypted=excluded.payload_encrypted, platform=excluded.platform, org_id=excluded.org_id",
            (payload.name, blob, payload.platform, data.get("org_id"), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        
        # Ensure customer folder exists
        ensure_env_files(payload.name)
        
        return {
            "status": "OK",
            "normalized_url": data.get("cucm_url") if platform == "CUCM" else None
            }
    finally:
        conn.close()
        
@app.get("/api/envs/{name}")
def get_env(name: str, passphrase: str | None = None) -> Dict[str, Any]:
    passphrase = passphrase or os.getenv("APP_PASSPHRASE")
    if not passphrase:
        raise HTTPException(status_code=400, detail="passphrase is required (query param passphrase or APP_PASSPHRASE)")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT payload_encrypted, platform, org_id FROM envs WHERE name=?", (name,))
    row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Environment not found")

    try:
        blob = row[0]
        if isinstance(blob, str):
            blob = blob.encode("utf-8")

        env = decrypt_json(passphrase, blob)
        env["platform"] = row[1]
        env["org_id"] = row[2]
    except Exception:
        raise HTTPException(
            status_code=403,
            detail="Invalid passphrase or corrupted environment"
        )

    env["cucm_password"] = ""  # never return secrets
    return env

@app.post("/api/envs/test")
def test_env(name: str, passphrase: str):
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload_encrypted, platform, org_id FROM envs WHERE name=?", (name,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Environment not found")

        try:
            env = decrypt_json(passphrase, row[0])
        except Exception:
            raise HTTPException(status_code=403, detail="Invalid passphrase")

        platform = env.get("platform", "CUCM").upper()

        # 🔹 CUCM ENGINE
        if platform == "CUCM":
            client = build_client(env)
            xml = client.get_version()

            return {
                "status": "ok",
                "platform": "CUCM",
                "message": "AXL authentication successful",
                "raw_response_snippet": xml[:300],
            }

        # 🔹 WEBEX ENGINE
        elif platform == "WEBEX":
            try:
                access_token = env.get("access_token")
                if not access_token:
                    raise HTTPException(status_code=400, detail="Missing Webex access token")
            
                webex = Webex(access_token=access_token)

                org = webex.org
                
                # # 🔎 DEBUG HERE
                # print("DEBUG ORG TYPE:", type(org))
                # print("DEBUG ORG DIR:", dir(org))
                # print("DEBUG ORG VARS:", vars(org))
                
                return {
                    "status": "ok",
                    "platform": "WEBEX",
                    "message": f"Connected to Webex Org: {org.name}",
                    "org_id": org.id,
                }

            except Exception as e:
                error_text = str(e)

                # Detect expired / invalid token
                if "401" in error_text or "not accepted" in error_text.lower():
                    raise HTTPException(
                        status_code=401,
                        detail={
                            "type": "token_expired",
                            "message": "Your Webex developer token has expired.",
                            "token_url": "https://developer.webex.com/docs/getting-started"
                        }
                    )

                raise HTTPException(
                    status_code=401,
                    detail=f"Webex authentication failed: {error_text}"
                )

    finally:
        conn.close()

@app.get("/api/dialplans/{env_name}")
def get_dialplan(env_name: str):
    path = resolve_dialplan_path(env_name)
    if not path:
        raise HTTPException(404, "Dialplan not found")

    return {
        "env_name": env_name,
        "dialplan": yaml.safe_load(Path(path).read_text())
    }
    
@app.post("/api/dialplans/{env_name}/render")
def render_dialplan(env_name: str, payload: dict):
    path = resolve_dialplan_path(env_name)
    dialplan = yaml.safe_load(Path(path).read_text())

    ctx = payload  # site, site_name, city, state, org

    partitions = []
    for k, p in dialplan["partitions"].items():
        if p.get("scope") == "site":
            partitions.append({
                "key": k,
                "name": p["name"].format(**ctx),
                "description": p.get("description","").format(**ctx)
            })

    css = []
    globals_p = dialplan["globals"]["partitions"]

    for k, c in dialplan["css"].items():
        members = []
        for m in c["members"]:
            if m in globals_p:
                members.append({"alias": m, "type": "global", "name": globals_p[m]})
            else:
                members.append({"alias": m, "type": "site", "name": m})

        css.append({
            "key": k,
            "name": c["name"].format(**ctx),
            "description": c.get("description","").format(**ctx),
            "members": members
        })

    return {
        "partitions": partitions,
        "css": css
    }
    
@app.post("/api/dialplans/{env_name}/verify-globals")
def verify_globals(env_name: str, payload: VerifyGlobalsRequest):
    passphrase = payload.passphrase

    env = load_env_internal(env_name, passphrase)

    platform = env.get("platform", "CUCM").upper()

    if platform != "CUCM":
        raise HTTPException(
            status_code=400,
            detail="Global verification only supported for CUCM environments"
        )

    # Default path (CUCM or anything else handled inside build_client)
    client = build_client(env)

    path = resolve_dialplan_path(env_name)
    if not path:
        raise HTTPException(status_code=404, detail="Dialplan not found")

    dialplan = yaml.safe_load(Path(path).read_text())

    # Normalize existing CUCM partitions
    existing = {p.strip() for p in client.list_partitions()}

    globals_section = dialplan.get("globals", {})
    globals_section = dialplan.get("globals", {})
    global_partitions_map = globals_section.get("partitions", {})

    # Only validate REAL partition names (values)
    global_partitions = [
        v.strip() for v in global_partitions_map.values() if v
    ]

    existing = {p.strip() for p in client.list_partitions()}

    found = []
    missing = []

    for name in global_partitions:
        if name in existing:
            found.append(name)
        else:
            missing.append(name)

    return {
        "found": sorted(found),
        "missing": sorted(missing),
    }

    # Also collect CSS members
    css_partitions = set()

    for css in dialplan.get("css", {}).values():
        for m in css.get("members", []):
            css_partitions.add(m)

    all_partitions = global_partitions.union(css_partitions)
    
    print("YAML globals:", repr(list(global_partitions)))
    print("AXL partitions:", repr(list(existing)))
    
    found = []
    missing = []

    for name in all_partitions:
        if not name:
            continue

        normalized = name.strip()

        if normalized in existing:
            found.append(normalized)
        else:
            missing.append(normalized)

    return {
        "found": sorted(found),
        "missing": sorted(missing),
    }

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    data_dir = Path(os.getenv("APP_DATA_DIR", "/data"))
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    upload_id = str(uuid.uuid4())
    stored_path = uploads_dir / f"{upload_id}.csv"

    content = await file.read()
    stored_path.write_bytes(content)

    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO uploads(id, filename, stored_path, created_at) VALUES(?,?,?,?)",
            (upload_id, file.filename, str(stored_path), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return {"upload_id": upload_id, "filename": file.filename}

class PlanRequest(BaseModel):
    upload_id: str
    env_name: str
    org: Optional[str] = None

@app.post("/api/plan")
def create_plan(req: PlanRequest):
    print("DEBUG: create_plan called")
    print("DEBUG: upload_id =", req.upload_id)
    print("DEBUG: env_name =", req.env_name)
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stored_path FROM uploads WHERE id=?", (req.upload_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="upload_id not found")
        stored_path = Path(row[0])

        # parse CSV -> SiteRow list
        rows = parse_site_rows(stored_path)

        # load naming profile
        naming_path = resolve_naming_path(req.env_name)

        if not Path(naming_path).exists():
            print("WARNING: naming.yml not found, falling back to default")
            naming_path = os.getenv("APP_DEFAULT_NAMING", "/app/naming.yml")
            
        dialplan_path = resolve_dialplan_path(req.env_name)

        naming = NamingProfile.load(
            naming_path=naming_path,
            dialplan_path=dialplan_path
        )

        if dialplan_path:
            print(f"DEBUG: Loaded dialplan {dialplan_path}")
        else:
            print(f"DEBUG: No dialplan found for {req.env_name}, at {dialplan_path}, continuing without dialplan") 

        org = (req.org or os.getenv("APP_ORG", "US")).strip().upper()

        # For Phase 1, we do not call CUCM; exists_lookup omitted.
        plan_result = build_plan(rows=rows, naming=naming, org=org, env_name=req.env_name)

        # Save plan
        plan_id = plan_result.plan_id
        cur.execute(
            "INSERT INTO plans(id, upload_id, env_name, plan_json, created_at) VALUES(?,?,?,?,?)",
            (
                plan_id,
                req.upload_id,
                req.env_name,
                json.dumps({"plan": plan_result.plan, "errors": plan_result.errors, "warnings": plan_result.warnings}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

        return {
            "plan_id": plan_id,
            "errors": plan_result.errors,
            "warnings": plan_result.warnings,
            "plan": plan_result.plan,
        }
    finally:
        conn.close()

class ExecuteRequest(BaseModel):
    plan_id: str
    passphrase: str


@app.post("/api/execute")
def execute(req: ExecuteRequest):
    conn = db_connect()
    try:
        cur = conn.cursor()

        # 1) Load plan + env_name
        cur.execute("SELECT plan_json, env_name FROM plans WHERE id=?", (req.plan_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="plan_id not found")

        plan_payload = json.loads(row[0])
        env_name = row[1]

        # your plan is stored as {"plan": ..., "errors": ..., "warnings": ...}
        plan = plan_payload.get("plan")
        if not plan:
            raise HTTPException(status_code=400, detail="Plan payload missing 'plan'")

        # 2) Load + decrypt environment by env_name
        cur.execute("SELECT payload_encrypted, platform FROM envs WHERE name=?", (env_name,))
        env_row = cur.fetchone()
        if not env_row:
            raise HTTPException(status_code=404, detail=f"Environment not found for plan: {env_name}")

        try:
            env = decrypt_json(req.passphrase, env_row[0])
        except Exception:
            raise HTTPException(status_code=403, detail="Invalid passphrase")

        # 3) Build CUCM client
        platform = env.get("platform", "CUCM").upper()

        if platform == "WEBEX":
            raise HTTPException(status_code=501, detail="Webex engine not implemented yet")

        # Default path (CUCM or anything else handled inside build_client)
        client = build_client(env)

        # 4) Execute plan against CUCM
        try:
            result = execute_plan(plan, client, apply=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing plan: {e}")

        return result

    finally:
        conn.close()

def parse_site_rows(path: Path) -> List[SiteRow]:
    content = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV appears to have no header row")

    out: List[SiteRow] = []
    errors: List[str] = []
    for idx, raw in enumerate(reader, start=2):
        # normalize keys to lower snake-ish (assume headers already match)
        try:
            out.append(SiteRow(**{k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}))
        except Exception as e:
            errors.append(f"Row {idx}: {e}")
    if errors:
        raise HTTPException(status_code=400, detail={"message": "CSV validation failed", "errors": errors})
    return out


@app.get("/api/executions")
def list_executions():
    exec_dir = Path(os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions"))
    exec_dir.mkdir(parents=True, exist_ok=True)

    executions = []
    for f in sorted(exec_dir.glob("*.json")):
        if f.name.endswith(".rollback.json"):
            continue

        data = json.loads(f.read_text())
        executions.append({
            "plan_id": data.get("plan_id"),
            "env_name": data.get("env_name"),
            "started_at": data.get("started_at"),
            "status": data.get("status"),
        })

    return {
        "status": "OK",
        "executions": executions
    }


@app.get("/api/executions/{plan_id}")
def get_execution(plan_id: str):
    exec_dir = Path(os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions"))
    path = exec_dir / f"{plan_id}.json"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Execution not found")

    return json.loads(path.read_text())

class RollbackRequest(BaseModel):
    env_name: str
    plan_id: str
    passphrase: str | None = None
    apply: bool = False


def load_env_internal(name: str, passphrase: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload_encrypted, platform FROM envs WHERE name=?", (name,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Environment not found")

        blob = row[0]
        if isinstance(blob, str):
            blob = blob.encode("utf-8")

        return decrypt_json(passphrase, blob)

    finally:
        conn.close()

@app.get("/api/rollback/{plan_id}/preview")
def api_rollback_preview(plan_id: str):
    exec_dir = Path(os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions"))
    exec_path = exec_dir / f"{plan_id}.json"

    if not exec_path.exists():
        raise HTTPException(status_code=404, detail="Execution not found")

    execution = json.loads(exec_path.read_text())

    steps = execution.get("results", [])

    created = [
    s for s in steps
    if s.get("status") == "CREATED" and s.get("rollback")
]
    created.reverse()

    rollback_steps = [
    {
        "order": i + 1,
        "site_code": s.get("site_code"),
        "type": s.get("type"),
        "name": s.get("name"),
        "rollback": s.get("rollback"),
    }
    for i, s in enumerate(created)
]

    return {
        "status": "OK",
        "plan_id": plan_id,
        "execution_status": execution.get("status"),
        "rollback_count": len(rollback_steps),
        "rollback_steps": rollback_steps,
    }

@app.get("/api/rollback/{plan_id}/status")
def rollback_status(plan_id: str):
    exec_dir = Path(os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions"))
    rb_path = exec_dir / f"{plan_id}.rollback.json"

    if not rb_path.exists():
        return {
            "status": "NOT_STARTED",
            "plan_id": plan_id,
            "total_steps": 0,
            "completed_steps": 0,
            "current_step": None
        }

    return json.loads(rb_path.read_text())

@app.post("/api/rollback")
def api_rollback(req: RollbackRequest):
    try:
        exec_dir = Path(os.getenv("APP_DATA_EXECUTIONS_DIR", "/data/executions"))
        exec_path = exec_dir / f"{req.plan_id}.json"

        if not exec_path.exists():
            return JSONResponse(
                status_code=404,
                content={"status": "ERROR", "message": "Execution not found"}
            )

        execution = json.loads(exec_path.read_text())

        # 🔒 SAFETY CHECK: environment must match
        if execution.get("env_name") != req.env_name:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "ERROR",
                    "message": (
                        f"Rollback environment mismatch. "
                        f"Execution was run against '{execution.get('env_name')}', "
                        f"but rollback requested for '{req.env_name}'."
                    )
                }
            )

        # Only now do we unlock credentials
        if not req.passphrase:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "ERROR",
                    "message": "Passphrase is required for rollback"
                }
            )

        env = load_env_internal(
            name=req.env_name,
            passphrase=req.passphrase  # now guaranteed str
        )

        platform = env.get("platform", "CUCM").upper()

        if platform == "WEBEX":
            raise HTTPException(status_code=501, detail="Webex engine not implemented yet")

        # Default path (CUCM or anything else handled inside build_client)
        client = build_client(env)

        return rollback_plan(
            plan_id=req.plan_id,
            client=client,
            apply=req.apply
        )

    except Exception as e:
        # 🚑 ABSOLUTE LAST LINE OF DEFENSE
        return JSONResponse(
            status_code=500,
            content={
                "status": "ERROR",
                "message": str(e)
            }
        )
