# MCPBridge - Usage Examples

**Quick Navigation:**
- [Example 1: First-Time Setup](#example-1-first-time-setup)
- [Example 2: Register All BCH Agents](#example-2-register-all-bch-agents)
- [Example 3: Get Agent Card JSON](#example-3-get-agent-card-json)
- [Example 4: Start Protocol Servers](#example-4-start-protocol-servers)
- [Example 5: Discover External Agent](#example-5-discover-external-agent)
- [Example 6: Delegate Task to External Agent](#example-6-delegate-task-to-external-agent)
- [Example 7: Python API - Custom Tool Registration](#example-7-python-api--custom-tool-registration)
- [Example 8: MCP Stdio Server for Claude Desktop](#example-8-mcp-stdio-server-for-claude-desktop)
- [Example 9: Full Bridge Integration with AgentHealth](#example-9-full-bridge-integration-with-agenthealth)
- [Example 10: Task History and Monitoring](#example-10-task-history-and-monitoring)
- [Example 11: Custom Database and Ports](#example-11-custom-database-and-ports)
- [Example 12: Multi-Environment Setup](#example-12-multi-environment-setup)

---

## Example 1: First-Time Setup

**Scenario:** Fresh install, first time running MCPBridge.

**Steps:**
```bash
# Step 1: Clone the repo
git clone https://github.com/DonkRonk17/MCPBridge.git
cd MCPBridge

# Step 2: Verify Python version
python --version
# Expected: Python 3.8+

# Step 3: Run tests to confirm everything works
python test_mcpbridge.py
```

**Expected Output:**
```
======================================================================
  MCPBridge v1.0 - Test Suite
  Agent: ATLAS (Team Brain)
======================================================================
test_basic_construction ... ok
test_to_dict_required_fields ... ok
...
----------------------------------------------------------------------
Ran 67 tests in 0.332s

OK
======================================================================
  RESULTS: 67 tests run
  [OK] Passed: 67
  [OK] ALL TESTS PASSED
======================================================================
```

**Step 4: Check version:**
```bash
python mcpbridge.py --version
# MCPBridge v1.0.0
```

**What You Learned:**
- How to install MCPBridge (just clone, no pip install needed)
- How to run the test suite
- How to verify the version

---

## Example 2: Register All BCH Agents

**Scenario:** Register all 5 Team Brain agents (ATLAS, FORGE, CLIO, NEXUS, BOLT) so they
are discoverable via A2A protocol.

**Steps:**
```bash
# Register all agents at once
python mcpbridge.py register --all
```

**Expected Output:**
```
[OK] Registered: ATLAS
[OK] Registered: BOLT
[OK] Registered: CLIO
[OK] Registered: FORGE
[OK] Registered: NEXUS
```

**Then verify:**
```bash
python mcpbridge.py list
```

**Expected Output:**
```
Name                 URL                                                Skills
------------------------------------------------------------------------------------------
ATLAS                http://localhost:8766/agents/atlas                 atlas_build, atlas_test
BOLT                 http://localhost:8766/agents/bolt                  bolt_execute
CLIO                 http://localhost:8766/agents/clio                  clio_linux
FORGE                http://localhost:8766/agents/forge                 forge_review, forge_spec
NEXUS                http://localhost:8766/agents/nexus                 nexus_arch

Total: 5 agents
```

**Or register a single agent:**
```bash
python mcpbridge.py register --agent ATLAS
# [OK] Registered: ATLAS
```

**What You Learned:**
- How to register all BCH agents with `--all`
- How to register a single specific agent
- How to verify registrations with `list`

---

## Example 3: Get Agent Card JSON

**Scenario:** Export a BCH agent's A2A-compliant agent card as JSON for sharing
with external systems or inspection.

**Steps:**
```bash
python mcpbridge.py card --agent ATLAS
```

**Expected Output:**
```json
{
  "name": "ATLAS",
  "description": "Implementation Lead and Quality Assurance Expert. Builds production-quality tools following Holy Grail Protocol. Specializes in Python development, testing, and Team Brain tooling.",
  "url": "http://localhost:8766/agents/atlas",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "skills": [
    {
      "id": "atlas_build",
      "name": "Build Tool",
      "description": "Build a Python tool following Holy Grail Protocol",
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain", "application/json"]
    },
    {
      "id": "atlas_test",
      "name": "Test Code",
      "description": "Write and run comprehensive test suite",
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain"]
    }
  ],
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "authentication": {"schemes": ["none"]},
  "provider": {
    "organization": "Metaphy LLC",
    "url": "https://github.com/DonkRonk17"
  }
}
```

**Save to file:**
```bash
python mcpbridge.py card --agent FORGE > forge_agent_card.json
```

**What You Learned:**
- How to export agent cards as A2A-compliant JSON
- Card structure includes skills, capabilities, authentication
- Can pipe to file for sharing with external systems

---

## Example 4: Start Protocol Servers

**Scenario:** Start both MCP (port 8765) and A2A (port 8766) servers so external
systems can connect to BCH agents.

**Steps:**
```bash
# Start with default ports
python mcpbridge.py serve
```

**Expected Output:**
```
[OK] MCPBridge running
     MCP server:  http://localhost:8765/mcp
     A2A server:  http://localhost:8766
     Agent cards: http://localhost:8766/.well-known/agent.json
     Press Ctrl+C to stop
```

**Verify MCP server health:**
```bash
# In a new terminal:
curl http://localhost:8765/health
# {"status": "ok", "service": "MCPBridge"}
```

**Verify A2A discovery:**
```bash
curl http://localhost:8766/.well-known/agent.json
# Returns ATLAS agent card (first registered agent)

curl http://localhost:8766/agents
# Returns all registered agents
```

**Custom ports:**
```bash
python mcpbridge.py serve --mcp-port 9765 --a2a-port 9766
```

**With verbose logging:**
```bash
python mcpbridge.py serve --verbose
```

**What You Learned:**
- How to start both protocol servers
- Health check endpoints for monitoring
- A2A discovery endpoint location
- How to use custom ports and verbose mode

---

## Example 5: Discover External Agent

**Scenario:** CLIO wants to discover an external research agent and add it
to BCH's capability registry.

**CLI:**
```bash
python mcpbridge.py discover --url http://research-agent.example.com
```

**Expected Output (success):**
```
[...] Discovering agent at: http://research-agent.example.com
[OK] Discovered: ResearchBot
     Description: Specialized RAG agent for academic research...
     URL:         http://research-agent.example.com/api/a2a
     Skills:      3
```

**Expected Output (failure):**
```
[X] Discovery failed for: http://research-agent.example.com
```

**Python API:**
```python
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()

# Discover and auto-register
card = bridge.discover_external_agent("http://research-agent.example.com")
if card:
    print(f"Found: {card.name}")
    print(f"Skills: {[s['id'] for s in card.skills]}")
    print(f"Capabilities: {card.capabilities}")
else:
    print("Discovery failed (agent not A2A compliant or offline)")
```

**Verify it was registered:**
```bash
python mcpbridge.py list
# Now shows ResearchBot alongside BCH agents
```

**What You Learned:**
- How to discover external A2A agents
- Discovered agents auto-register in local registry
- Graceful failure when agent is unreachable or not A2A compliant

---

## Example 6: Delegate Task to External Agent

**Scenario:** ATLAS needs a specialized security analysis that an external
AI agent performs. Delegate the task via A2A.

**CLI:**
```bash
python mcpbridge.py delegate \
  --url http://security-analyzer.example.com \
  --message "Analyze this Python function for SQL injection vulnerabilities: def get_user(id): return db.execute(f'SELECT * FROM users WHERE id={id}')"
```

**Expected Output:**
```
[...] Delegating task to: http://security-analyzer.example.com
[OK] Task ID:  3f7a2bc1-9d4e-4f8a-b2c3-1a2b3c4d5e6f
     Status:   pending
```

**Python API with status polling:**
```python
from mcpbridge import ProtocolBridge, A2AClientModule
import time

bridge = ProtocolBridge()
client = bridge.a2a_client

# Delegate
task = bridge.delegate_to_external(
    "http://security-analyzer.example.com",
    "Perform security audit on the provided code"
)
print(f"Task {task.task_id} - Status: {task.status}")

# Poll for completion (simple backoff)
for wait in [2, 4, 8, 15, 30]:
    time.sleep(wait)
    updated = client.poll_task("http://security-analyzer.example.com", task.task_id)
    print(f"Status: {updated.status}")
    if updated.status in ("completed", "failed"):
        print(f"Result: {updated.result or updated.error}")
        break
```

**What You Learned:**
- How to delegate tasks to external A2A agents
- Task polling pattern with exponential backoff
- Task IDs for tracking delegated work
- Result and error handling for completed tasks

---

## Example 7: Python API — Custom Tool Registration

**Scenario:** FORGE registers with MCPBridge exposing custom MCP tools
that external MCP clients can call.

```python
from mcpbridge import (
    ProtocolBridge, MCPTool, MCPResource, MCPPrompt
)
from pathlib import Path
import time

# Initialize bridge
bridge = ProtocolBridge(
    mcp_port=8765,
    a2a_port=8766,
    log_path=Path("~/.mcpbridge/forge.log").expanduser()
)

# Define FORGE's MCP tools
forge_tools = [
    MCPTool(
        name="review_code",
        description="Review code and provide architectural feedback",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Code to review"},
                "language": {"type": "string", "description": "Programming language"},
                "focus": {
                    "type": "string",
                    "enum": ["security", "performance", "style", "architecture"],
                    "description": "Review focus area"
                }
            },
            "required": ["code"]
        }
    ),
    MCPTool(
        name="write_spec",
        description="Write a technical specification for a new tool",
        input_schema={
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "purpose": {"type": "string"},
                "target_users": {"type": "string"}
            },
            "required": ["tool_name", "purpose"]
        }
    ),
]

# Define FORGE's MCP resources
forge_resources = [
    MCPResource(
        uri="bch://forge/session",
        name="Current Session",
        description="FORGE current session state"
    ),
]

# Define FORGE's MCP prompts
forge_prompts = [
    MCPPrompt(
        name="architecture_review",
        description="Review system architecture",
        arguments=[
            {"name": "context", "description": "System context", "required": True},
            {"name": "constraints", "description": "Known constraints", "required": False}
        ]
    )
]

# Register FORGE
card = bridge.register_bch_agent(
    agent_name="FORGE",
    description="Orchestrator and Reviewer",
    tools=forge_tools,
    resources=forge_resources,
    prompts=forge_prompts
)

# Wire up tool handlers
mcp = bridge.get_mcp_handler("FORGE")
mcp.register_tool_handler(
    "review_code",
    lambda args: f"[FORGE Review] Code reviewed. Focus: {args.get('focus', 'general')}. Looks good architecturally."
)
mcp.register_tool_handler(
    "write_spec",
    lambda args: f"[FORGE Spec] Spec written for {args['tool_name']}: {args['purpose']}"
)
mcp.register_resource_handler(
    "bch://forge/session",
    lambda: '{"agent": "FORGE", "status": "active", "current_task": "orchestrating"}'
)
mcp.register_prompt_handler(
    "architecture_review",
    lambda args: [{
        "role": "user",
        "content": {"type": "text", "text": f"Review architecture for: {args.get('context', '')}"}
    }]
)

# Start serving
bridge.start_servers()
print(f"FORGE online at {card.url}")
print(f"MCP: http://localhost:8765/mcp")

# Keep running
try:
    while True:
        time.sleep(10)
        status = bridge.status()
        print(f"Bridge status: {status['registered_agents']} agents")
except KeyboardInterrupt:
    bridge.stop_servers()
    print("Stopped")
```

**What You Learned:**
- Full Python API for registering agents with tools, resources, and prompts
- How to wire up handler functions for each capability
- How to start/stop servers programmatically
- Server lifecycle management in background threads

---

## Example 8: MCP Stdio Server for Claude Desktop

**Scenario:** Configure Claude Desktop to use BCH tools via MCPBridge stdio transport.

**Step 1: Create a simple BCH MCP stdio script:**
```python
# bch_mcp_stdio.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from mcpbridge import MCPProtocol, MCPTool, MCPStdioAdapter

# BCH tools to expose to Claude
tools = [
    MCPTool("list_bch_agents", "List all Team Brain agents and their status"),
    MCPTool("get_synapse_messages", "Get recent messages from BCH Synapse"),
    MCPTool("send_synapse_message", "Send a message via BCH SynapseLink",
            {"type": "object", "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            }}),
    MCPTool("check_tool_registry", "Check available tools in AutoProjects"),
]

proto = MCPProtocol(server_name="BCH-Atlas-Bridge", tools=tools)

# Wire handlers to actual BCH functions
proto.register_tool_handler("list_bch_agents",
    lambda a: "ATLAS, FORGE, CLIO, NEXUS, BOLT - all active")
proto.register_tool_handler("get_synapse_messages",
    lambda a: "No unread messages")
proto.register_tool_handler("send_synapse_message",
    lambda a: f"Message sent to {a.get('to', 'TEAM')}")
proto.register_tool_handler("check_tool_registry",
    lambda a: "77 tools registered in AutoProjects")

# Run stdio server
adapter = MCPStdioAdapter(proto)
adapter.run()
```

**Step 2: Add to Claude Desktop config:**

File: `%APPDATA%\Claude\claude_desktop_config.json` (Windows)
```json
{
  "mcpServers": {
    "bch-bridge": {
      "command": "python",
      "args": [
        "C:\\Users\\logan\\OneDrive\\Documents\\AutoProjects\\MCPBridge\\bch_mcp_stdio.py"
      ]
    }
  }
}
```

**Step 3: Restart Claude Desktop.**

Now Claude can use BCH tools directly in conversations:
- "List the Team Brain agents"
- "Send a Synapse message to FORGE about the new build"

**What You Learned:**
- MCP stdio transport for Claude Desktop integration
- How to expose BCH functionality as MCP tools
- Claude Desktop config file format and location

---

## Example 9: Full Bridge Integration with AgentHealth

**Scenario:** ATLAS integrates MCPBridge with AgentHealth to track protocol
server health alongside agent session monitoring.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # AutoProjects root

from mcpbridge import ProtocolBridge, AgentCardGenerator

# Initialize both tools
bridge = ProtocolBridge()

# Register all BCH agents in MCPBridge
cards = AgentCardGenerator.generate_all()
for card in bridge.registry.list_agents() or []:
    pass  # Already registered

bridge.registry.register_agent(AgentCardGenerator.generate_for_agent("ATLAS"))

# Try to import AgentHealth (optional integration)
try:
    from agenthealth import AgentHealth
    health = AgentHealth()
    session_id = f"mcpbridge_session_{id(bridge)}"
    health.start_session("ATLAS", session_id=session_id, context="MCPBridge active")
    has_health = True
except ImportError:
    has_health = False
    print("[!] AgentHealth not available - bridge running without health monitoring")

# Start bridge
bridge.start_servers()
status = bridge.status()
print(f"[OK] Bridge online: {status['registered_agents']} agents registered")

if has_health:
    health.heartbeat("ATLAS", context="MCP/A2A servers running")

# Simulate some activity
card = bridge.discover_external_agent("http://external.example.com")
if card:
    task = bridge.delegate_to_external(card.url, "Test task")
    print(f"[OK] Delegated task: {task.task_id}")
else:
    print("[!] External agent not available (expected in test env)")

# Cleanup
bridge.stop_servers()
if has_health:
    health.end_session("ATLAS", session_id=session_id, status="success")
print("[OK] Session complete")
```

**What You Learned:**
- How to optionally integrate with AgentHealth
- Graceful degradation when optional tools are unavailable
- Proper session lifecycle: start → heartbeat → end
- Using `try/import` pattern for optional Team Brain tool integration

---

## Example 10: Task History and Monitoring

**Scenario:** FORGE wants to audit all tasks delegated to external agents
over the past week.

**CLI:**
```bash
# Show recent tasks (all agents)
python mcpbridge.py tasks

# Show tasks for specific agent
python mcpbridge.py tasks --agent ATLAS

# Show more tasks
python mcpbridge.py tasks --limit 100
```

**Expected Output:**
```
Task ID                                Agent                Status       Message
----------------------------------------------------------------------------------------------------
3f7a2bc1-9d4e-4f8a-b2c3-1a2b3c4d5e6f  ATLAS                completed    Analyze this Python fun...
a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d  FORGE                pending      Review architecture for...
...

Showing 2 tasks
```

**Python API:**
```python
from mcpbridge import CapabilityRegistry, STATUS_COMPLETED, STATUS_FAILED
from pathlib import Path

registry = CapabilityRegistry(Path("~/.mcpbridge/registry.db").expanduser())

# Get all tasks
all_tasks = registry.list_tasks(limit=100)
print(f"Total tasks: {len(all_tasks)}")

# Filter by status
completed = [t for t in all_tasks if t.status == STATUS_COMPLETED]
failed = [t for t in all_tasks if t.status == STATUS_FAILED]
print(f"Completed: {len(completed)}, Failed: {len(failed)}")

# Get tasks for specific agent
atlas_tasks = registry.list_tasks(agent_name="ATLAS", limit=50)
for task in atlas_tasks:
    print(f"  {task.task_id[:8]}... {task.status:12} {task.message[:50]}")

# Get specific task
task = registry.get_task("3f7a2bc1-9d4e-4f8a-b2c3-1a2b3c4d5e6f")
if task:
    print(f"Task details:")
    print(f"  Agent: {task.agent_name}")
    print(f"  Status: {task.status}")
    print(f"  Result: {task.result}")
    print(f"  Created: {task.created_at}")
```

**What You Learned:**
- CLI task listing with optional agent filter
- Python API for task querying and filtering
- Status constants for programmatic filtering
- Task detail retrieval by ID

---

## Example 11: Custom Database and Ports

**Scenario:** Running multiple MCPBridge instances for different projects
or environments (dev vs. production).

```bash
# Development setup
python mcpbridge.py --db ./dev/agents.db --mcp-port 8765 --a2a-port 8766 register --all
python mcpbridge.py --db ./dev/agents.db --mcp-port 8765 --a2a-port 8766 serve

# Production setup (different ports, persistent DB)
python mcpbridge.py \
  --db D:\BEACON_HQ\mcpbridge_prod.db \
  --mcp-port 9765 \
  --a2a-port 9766 \
  --host 0.0.0.0 \
  register --all

python mcpbridge.py \
  --db D:\BEACON_HQ\mcpbridge_prod.db \
  --mcp-port 9765 \
  --a2a-port 9766 \
  serve
```

**Python API with custom config:**
```python
from mcpbridge import ProtocolBridge
from pathlib import Path

# Dev bridge
dev_bridge = ProtocolBridge(
    db_path=Path("./dev/agents.db"),
    mcp_port=8765,
    a2a_port=8766,
    log_path=Path("./dev/bridge.log"),
    verbose=True
)

# Prod bridge
prod_bridge = ProtocolBridge(
    db_path=Path("D:/BEACON_HQ/mcpbridge_prod.db"),
    mcp_port=9765,
    a2a_port=9766,
    log_path=Path("D:/BEACON_HQ/mcpbridge_prod.log"),
    verbose=False
)

# Each uses independent database and port space
```

**What You Learned:**
- Custom database paths for project isolation
- Custom port configuration for parallel environments
- Verbose logging for development/debugging
- Python API configuration options

---

## Example 12: Multi-Environment Setup

**Scenario:** Team Brain uses MCPBridge in a full production setup where
all 5 agents are registered, servers are running, and external discovery
is active.

```python
#!/usr/bin/env python3
"""
BCH Production MCPBridge Setup
Run at Team Brain startup to enable Internet of Agents connectivity.
"""
import signal
import sys
import time
from pathlib import Path

# Add AutoProjects to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import (
    ProtocolBridge, MCPTool, AgentCardGenerator
)

def main():
    print("=" * 60)
    print("  BCH MCPBridge - Production Setup")
    print("  Enabling Internet of Agents for Team Brain")
    print("=" * 60)

    # Initialize with production paths
    bridge = ProtocolBridge(
        db_path=Path("D:/BEACON_HQ/mcpbridge.db"),
        mcp_port=8765,
        a2a_port=8766,
        log_path=Path("D:/BEACON_HQ/mcpbridge.log"),
        verbose=False
    )

    # Register all BCH agents
    print("[...] Registering BCH agents...")
    all_cards = AgentCardGenerator.generate_all()
    for card in all_cards:
        bridge.registry.register_agent(card)
        print(f"  [OK] {card.name}")

    # Register ATLAS with full MCP toolset
    atlas_tools = [
        MCPTool("build_python_tool", "Build a Python tool"),
        MCPTool("run_test_suite", "Run test suite and report"),
        MCPTool("check_quality_gates", "Verify quality gates"),
    ]
    bridge.register_bch_agent("ATLAS", "Builder", tools=atlas_tools)
    mcp = bridge.get_mcp_handler("ATLAS")
    mcp.register_tool_handler("build_python_tool", lambda a: "Build started")
    mcp.register_tool_handler("run_test_suite", lambda a: "Tests: 67/67 passing")
    mcp.register_tool_handler("check_quality_gates", lambda a: "All 6 gates: PASS")

    # Start servers
    bridge.start_servers()
    status = bridge.status()

    print(f"\n[OK] MCPBridge running")
    print(f"     Agents:      {status['registered_agents']}")
    print(f"     MCP server:  http://localhost:{status['mcp_port']}/mcp")
    print(f"     A2A server:  http://localhost:{status['a2a_port']}")
    print(f"     Discovery:   http://localhost:{status['a2a_port']}/.well-known/agent.json")
    print(f"\n     Press Ctrl+C to stop")

    # Graceful shutdown
    def shutdown(sig, frame):
        print("\n[...] Shutting down MCPBridge...")
        bridge.stop_servers()
        print("[OK] Stopped cleanly")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    # Health monitoring loop
    while True:
        time.sleep(60)
        status = bridge.status()
        print(f"[Health] {status['registered_agents']} agents | "
              f"{status['recent_tasks']} recent tasks")

if __name__ == "__main__":
    main()
```

**Expected Output:**
```
============================================================
  BCH MCPBridge - Production Setup
  Enabling Internet of Agents for Team Brain
============================================================
[...] Registering BCH agents...
  [OK] ATLAS
  [OK] BOLT
  [OK] CLIO
  [OK] FORGE
  [OK] NEXUS

[OK] MCPBridge running
     Agents:      5
     MCP server:  http://localhost:8765/mcp
     A2A server:  http://localhost:8766
     Discovery:   http://localhost:8766/.well-known/agent.json

     Press Ctrl+C to stop
[Health] 5 agents | 0 recent tasks
```

**What You Learned:**
- Production deployment pattern with signal handling
- Full agent registration with MCP tool handlers
- Health monitoring loop pattern
- Graceful shutdown with signal handling

---

*MCPBridge v1.0 — Built by ATLAS (Team Brain) — February 21, 2026*
