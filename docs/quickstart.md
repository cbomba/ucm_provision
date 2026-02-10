🚀 Quick Start

This section covers the minimum steps required to design, visualize, verify, and execute a CUCM dial plan using this tool.

The intended workflow is:

write YAML → preview visually → verify globals → execute safely

⸻

1️⃣ Clone the Repository

```git clone https://github.com/your-org/ucm-site-provisioner.git```
```cd ucm-site-provisioner```

⸻

🖥️ Start the Application

Run the application using Docker:

docker compose up --build

Once running, access the UI at:

http://localhost:8080/index.html


⸻

📁 Create a Dial Plan

Dial plans are defined as YAML files and stored per environment.

Directory structure:

/data/dialplans/customers/\<environment-slug\>/dialplan.yml

Example:

/data/dialplans/customers/s4n-prod-cluster/dialplan.yml

Notes:
	•	The environment slug must match the environment name shown in the UI
	•	YAML is the source of truth
	•	The UI does not modify YAML directly

⸻

Edit sites.csv to Define Your Sites

The application uses sites.csv to define site-level metadata that can be imported or referenced during provisioning.

📍 You must edit this file before importing real sites.

File location:
data/sites.csv

Example sites.csv
\<Sample data here\>


⸻

🔐 Unlock an Environment

Before interacting with any environment, you must:
	•	Enter the passphrase
	•	Select an environment
	•	Click Test Connection

Until this succeeds:
	•	Dial plans cannot be loaded
	•	Globals cannot be verified
	•	Execution is disabled

This prevents accidental changes to the wrong CUCM cluster.

⸻

👀 Visualize the Dial Plan

After a successful connection test:
	•	Click Load Dial Plan
	•	Enter example site details (site code, name, city, state)
	•	Click Render Example

The UI will display:
	•	Site-specific partitions
	•	Calling Search Spaces (CSS)
	•	Global vs site partition membership
	•	Unresolved or unverified globals (if applicable)

No changes are made to CUCM during this step.

⸻

🔍 Verify Global Partitions

Global partitions referenced by the dial plan can be verified against CUCM.

When connected:
	•	Existing globals are marked as verified
	•	Missing globals are highlighted

When offline:
	•	Globals remain unverified
	•	Execution is still possible if verification is intentionally skipped

This step is read-only and safe.

⸻

⚙️ Execute the Plan

When satisfied with the preview:
	•	Navigate to the Execute section
	•	Review the plan summary
	•	Click Execute Plan

Execution:
	•	Runs objects in dependency order
	•	Displays real-time progress
	•	Records full execution metadata

⸻

🔄 Roll Back if Needed

Every execution automatically generates rollback metadata.

From the Rollback page you can:
	•	Preview rollback actions
	•	See exactly which objects will be removed
	•	Execute rollback in reverse dependency order

No manual cleanup is required.
