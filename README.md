# UCM Site Provisioner – Dial Plan Designer & Executor

This project provides a **safe, visual, and auditable way to design, validate, and execute Cisco Unified Communications Manager (CUCM) dial plan objects** using YAML, AXL, and a lightweight web UI.

It is intentionally opinionated toward **repeatable site-based deployments** while still allowing flexibility for customer-specific standards.

---

## 🧠 Why This Exists

Provisioning dial plan objects directly in CUCM is:
- Manual
- Error-prone
- Hard to audit
- Difficult to reproduce consistently across environments

This tool solves that by introducing a **design → visualize → verify → execute** workflow.

Key goals:
- Make dial plans **declarative**
- Catch mistakes **before execution**
- Make rollbacks **predictable**
- Keep engineers out of CUCM GUI as much as possible

---

## 🧩 Core Concepts

### Dial Plan as Code
Dial plans are defined in YAML and stored alongside customer environments.

YAML is the **source of truth**.  
The UI exists to **visualize and validate**, not replace YAML.

### Environment Isolation
Each CUCM environment:
- Has its own credentials
- Has its own dial plan directory
- Is explicitly selected and tested before use

### Safe by Default
- Credentials are encrypted at rest
- Passphrase required before *any* environment interaction
- Verification is separate from execution
- Rollback is always generated

---

## 🔁 Workflow Overview

### 1. Author the Dial Plan (YAML)
Create or edit a dial plan in:

/data/dialplans/customers//dialplan.yml

This includes:
- Global partitions (pre-existing objects)
- Site-based partitions
- Calling Search Spaces
- Supporting CUCM objects

YAML is designed to be **human-readable and reviewable**.

---

### 2. Open the Dial Plan Designer (Web UI)

The UI is reachable from:

index.html

The UI allows you to:
- Select an environment
- Unlock credentials with a passphrase
- Visualize the rendered dial plan
- See partition/CSS relationships
- Identify missing global dependencies

⚠️ **Nothing is created at this stage.**

---

### 3. Test Environment Connectivity

Before anything else:
- Enter the passphrase
- Select an environment
- Click **Test Connection**

This verifies:
- Credentials decrypt correctly
- AXL connectivity works
- The environment is reachable

Until this passes:
- The environment selector is locked
- Execution is disabled

---

### 4. Render a Sample Site

Use the **Example Site** section to render a hypothetical site:

- Site code
- Site name
- City / State

This dynamically generates:
- Site-specific partitions
- Calling Search Spaces
- Partition membership order

You can visually inspect:
- Partition names
- CSS ordering
- Global vs site partitions

---

### 5. Verify Global Dependencies

Global partitions **must already exist** in CUCM.

The **Verify Globals** action:
- Queries CUCM via AXL
- Compares against YAML globals
- Returns:
  - ✅ Found
  - ⚠ Missing

In the UI:
- Missing globals are highlighted
- Verified globals are marked
- Unverified globals are visually distinct

This step can be skipped for **offline design work**, but is required before execution.

---

### 6. Execute the Plan

Once satisfied:
- Execute the plan
- Progress is streamed live
- Each step is tracked and persisted

Execution output includes:
- Total steps
- Completed steps
- Current object being created
- Final status

---

### 7. Rollback (If Needed)

Every execution generates a rollback plan automatically.

Rollback:
- Only removes objects that were actually created
- Runs in reverse order
- Supports preview and execution modes
- Has its own progress tracking

Rollback is **safe, explicit, and auditable**.

---

## 🎨 UI Legend

The UI uses visual indicators to reduce ambiguity:

### Partition Type
- 🌐 Global partition
- 🏢 Site partition

### Verification Status
- ✅ Verified (exists in CUCM)
- ⚠ Missing (referenced but not found)
- ❓ Unverified (not yet checked)

A legend is displayed directly in the UI to keep this self-documenting.

---

## 🔐 Security Model

- CUCM credentials are encrypted at rest
- A passphrase is required to decrypt credentials
- The passphrase is **never stored**
- All destructive actions require confirmation
- Rollback is always available

---

## 🧰 Technical Stack

- **Backend:** FastAPI (Python)
- **Frontend:** Vanilla HTML / CSS / JS
- **Protocol:** Cisco AXL (SOAP)
- **Storage:** YAML + JSON execution artifacts
- **Auth:** HTTP Basic over TLS (AXL)

---

## 📁 Directory Structure
```md
/app
├── app/
│   ├── main.py
│   ├── integrations/
│   │   └── ucm_axl.py
│   └── models/
├── static/
│   ├── dialplan.js
│   ├── rollback.js
│   └── styles.css
/data
└── dialplans/
└── customers/
└── /
└── dialplan.yml
```
Execution and rollback artifacts are stored alongside the plan for traceability.

---

## ⚠️ Important Notes

- A partition being listed does **not** make it special  
  Partitions only matter when referenced by CSS
- CSS objects are expected **not** to exist prior to execution
- This tool does **not** auto-create missing globals
- Verification is advisory, not destructive

---

## 🚧 Design Philosophy

This tool is intentionally:
- Conservative
- Explicit
- Transparent

It favors:
- Human review over automation
- Visibility over speed
- Safety over convenience

---

## 🛣️ Future Enhancements

Potential additions:
- Offline / online toggle
- Dependency graph visualization
- Pre-execution blocking rules
- Diff view against existing CUCM state
- Multi-site batch rendering

---

## 📜 License / Disclaimer

This project interacts directly with CUCM using AXL.
Use with care in production environments.

Always test in lab or staging first.

---

## 🙌 Final Thought

If you wouldn’t trust a change in production without reviewing it in Git —
you shouldn’t trust it in CUCM either.

This tool exists to bring those worlds together.
