# MCPBridge - Integration Examples

**Copy-paste ready code for 10 common integration patterns.**

## Table of Contents

1. [MCPBridge + AgentHealth](#pattern-1-mcpbridge--agenthealth)
2. [MCPBridge + SynapseLink](#pattern-2-mcpbridge--synapselink)
3. [MCPBridge + TaskQueuePro](#pattern-3-mcpbridge--taskqueuepro)
4. [MCPBridge + MemoryBridge](#pattern-4-mcpbridge--memorybridge)
5. [MCPBridge + SessionReplay](#pattern-5-mcpbridge--sessionreplay)
6. [MCPBridge + ContextCompressor](#pattern-6-mcpbridge--contextcompressor)
7. [MCPBridge + ConfigManager](#pattern-7-mcpbridge--configmanager)
8. [MCPBridge + CollabSession](#pattern-8-mcpbridge--collabsession)
9. [Multi-Tool A2A Workflow](#pattern-9-multi-tool-a2a-workflow)
10. [Full Team Brain Stack](#pattern-10-full-team-brain-stack)

---

## Pattern 1: MCPBridge + AgentHealth

**Use Case:** Monitor MCPBridge protocol health alongside agent session health.

**Why:** Correlate network errors, discovery failures, and task completions with
agent health status for comprehensive system visibility.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge, AgentCardGenerator

try:
    from agenthealth import AgentHealth
    health = AgentHealth()
except ImportError:
    health = None

bridge = ProtocolBridge()
session_id = "atlas_mcpbridge_session"

if health:
    health.start_session("ATLAS", session_id=session_id,
                         context="MCPBridge: registering agents")

# Register all BCH agents
for card in AgentCardGenerator.generate_all():
    bridge.registry.register_agent(card)

# Start protocol servers
bridge.start_servers()

if health:
    health.heartbeat("ATLAS", context="MCPBridge servers active (MCP:8765, A2A:8766)")

# Discover external agent
card = bridge.discover_external_agent("http://external.example.com")
if card:
    if health:
        health.heartbeat("ATLAS", context=f"Discovered external: {card.name}")

# Cleanup
import time
time.sleep(5)  # Simulate work
bridge.stop_servers()

if health:
    health.end_session("ATLAS", session_id=session_id, status="success")
    print("[OK] Session health tracked with MCPBridge activity")
```

**Result:** AgentHealth session log contains MCPBridge milestones for debugging.

---

## Pattern 2: MCPBridge + SynapseLink

**Use Case:** Automatically notify Team Brain when new external agents are
discovered or when the bridge status changes.

**Why:** FORGE and Logan want to know about new AI capabilities in the ecosystem
without checking manually.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge

try:
    from synapselink import quick_send
    has_synapse = True
except ImportError:
    has_synapse = False

bridge = ProtocolBridge()

# Discovery with automatic team notification
def discover_and_notify(base_url: str):
    card = bridge.discover_external_agent(base_url)
    if card:
        if has_synapse:
            quick_send(
                "TEAM",
                f"New External Agent: {card.name}",
                f"Description: {card.description}\n"
                f"URL: {card.url}\n"
                f"Skills: {', '.join(s['id'] for s in card.skills)}\n"
                f"Registered in MCPBridge for A2A delegation.",
                priority="NORMAL"
            )
        return card
    return None

# Check multiple potential external agents
agent_urls = [
    "http://code-review-ai.example.com",
    "http://research-bot.example.com",
    "http://security-analyzer.example.com"
]

discovered = []
for url in agent_urls:
    card = discover_and_notify(url)
    if card:
        discovered.append(card)

# Weekly summary notification
if has_synapse and discovered:
    quick_send(
        "FORGE,LOGAN",
        f"MCPBridge Weekly: {len(discovered)} External Agents",
        "\n".join(f"- {c.name}: {len(c.skills)} skills" for c in discovered)
    )

print(f"[OK] Discovered {len(discovered)} agents, team notified")
```

**Result:** Team Brain stays informed of ecosystem changes without manual checks.

---

## Pattern 3: MCPBridge + TaskQueuePro

**Use Case:** Track A2A task delegations in the central task queue alongside
all other BCH tasks.

**Why:** FORGE needs unified visibility into all agent work — internal and
external — in one place.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge, STATUS_FAILED

try:
    from taskqueuepro import TaskQueuePro
    queue = TaskQueuePro()
except ImportError:
    queue = None

bridge = ProtocolBridge()

def delegate_tracked_task(agent_url: str, message: str, task_title: str = None):
    """Delegate A2A task with TaskQueuePro tracking."""
    queue_task_id = None
    
    if queue:
        queue_task_id = queue.create_task(
            title=task_title or f"A2A: {message[:50]}",
            agent="ATLAS",
            priority=2,
            metadata={"type": "a2a_delegation", "target": agent_url}
        )
        queue.start_task(queue_task_id)

    try:
        a2a_task = bridge.delegate_to_external(agent_url, message)
        
        if queue and queue_task_id:
            if a2a_task.status == STATUS_FAILED:
                queue.fail_task(queue_task_id, error=a2a_task.error)
            else:
                queue.complete_task(queue_task_id, result={
                    "a2a_task_id": a2a_task.task_id,
                    "status": a2a_task.status
                })
        
        return a2a_task
        
    except Exception as e:
        if queue and queue_task_id:
            queue.fail_task(queue_task_id, error=str(e))
        raise

# Usage
task = delegate_tracked_task(
    "http://code-analyzer.example.com",
    "Analyze security vulnerabilities in: def unsafe(input): exec(input)",
    "Security Analysis: Exec vulnerability check"
)
print(f"[OK] Task {task.task_id} created, tracked in queue")
```

**Result:** All agent work — local and delegated — visible in single task queue.

---

## Pattern 4: MCPBridge + MemoryBridge

**Use Case:** Persist discovered external agent catalog across sessions so
FORGE doesn't rediscover the same agents every time.

**Why:** Agent discovery takes network time; cache results for instant access.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge, AgentCard
from datetime import datetime, timezone

try:
    from memorybridge import MemoryBridge
    memory = MemoryBridge()
except ImportError:
    memory = None

bridge = ProtocolBridge()

def load_known_agents():
    """Load previously discovered agents from memory."""
    if not memory:
        return []
    return memory.get("mcpbridge_external_agents", default=[])

def save_known_agents(agents_data: list):
    """Persist agent catalog to memory."""
    if memory:
        memory.set("mcpbridge_external_agents", agents_data)
        memory.sync()

# Load previous session's discoveries
known = load_known_agents()
print(f"[Memory] {len(known)} agents from previous sessions")

# Register cached agents
for agent_data in known:
    card = AgentCard.from_dict(agent_data)
    bridge.registry.register_agent(card)
    print(f"  [OK] Restored: {card.name}")

# Discover new agents
new_urls = ["http://new-agent.example.com"]
newly_discovered = []

for url in new_urls:
    card = bridge.discover_external_agent(url)
    if card:
        card_data = card.to_dict()
        card_data["discovered_at"] = datetime.now(timezone.utc).isoformat()
        newly_discovered.append(card_data)
        print(f"  [OK] New: {card.name}")

# Persist combined catalog
all_agents = known + newly_discovered
save_known_agents(all_agents)
print(f"[OK] {len(all_agents)} total agents saved to memory")
```

**Result:** Discovery catalog persists across sessions; no redundant network calls.

---

## Pattern 5: MCPBridge + SessionReplay

**Use Case:** Record MCPBridge protocol activity for debugging and audit trails.

**Why:** If an A2A delegation fails or produces unexpected results, SessionReplay
lets ATLAS replay exactly what happened.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge

try:
    from sessionreplay import SessionReplay
    replay = SessionReplay()
except ImportError:
    replay = None

bridge = ProtocolBridge()

session_id = None
if replay:
    session_id = replay.start_session("ATLAS", task="MCPBridge: A2A discovery and delegation")

# Instrument discovery
if replay and session_id:
    replay.log_input(session_id, "Discovering: http://external.example.com")

card = bridge.discover_external_agent("http://external.example.com")

if card:
    if replay and session_id:
        replay.log_output(session_id, f"Discovered: {card.name} ({len(card.skills)} skills)")
    
    # Delegate a task
    if replay and session_id:
        replay.log_input(session_id, f"Delegating task to: {card.url}")
    
    task = bridge.delegate_to_external(card.url, "Analyze performance bottlenecks")
    
    if replay and session_id:
        replay.log_output(session_id, f"Task {task.task_id}: {task.status}")
    
    print(f"[OK] Task {task.task_id} delegated")
else:
    if replay and session_id:
        replay.log_output(session_id, "Discovery failed: agent not A2A compliant")
    print("[!] Discovery failed")

# End session
if replay and session_id:
    status = "COMPLETED" if card else "PARTIAL"
    replay.end_session(session_id, status=status)
    print(f"[OK] Session recorded with ID: {session_id}")
```

**Result:** Full replay available for every MCPBridge operation.

---

## Pattern 6: MCPBridge + ContextCompressor

**Use Case:** Compress large agent catalogs before including in Synapse messages
or session context.

**Why:** Registry can grow large with many external agents. Compress before
sharing to save tokens.

```python
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge

try:
    from contextcompressor import ContextCompressor
    compressor = ContextCompressor()
except ImportError:
    compressor = None

bridge = ProtocolBridge()

# Generate full agent catalog
from mcpbridge import AgentCardGenerator
cards = AgentCardGenerator.generate_all()
for card in cards:
    bridge.registry.register_agent(card)

agents = bridge.registry.list_agents()
full_catalog = json.dumps(
    [a.to_dict() for a in agents],
    indent=2
)

print(f"Full catalog size: {len(full_catalog)} chars (~{len(full_catalog)//4} tokens)")

if compressor:
    compressed = compressor.compress_text(
        full_catalog,
        query="agent capabilities and skills",
        method="summary"
    )
    print(f"Compressed size: {len(compressed.compressed_text)} chars")
    print(f"Compression ratio: {len(compressed.compressed_text)/len(full_catalog):.1%}")
    
    # Use compressed in Synapse
    try:
        from synapselink import quick_send
        quick_send("FORGE", "BCH Agent Catalog", compressed.compressed_text)
    except ImportError:
        pass
else:
    # Fallback: just summarize
    summary = f"{len(agents)} agents: " + ", ".join(a.name for a in agents)
    print(f"Summary: {summary}")
```

**Result:** Agent catalog shared efficiently without token waste.

---

## Pattern 7: MCPBridge + ConfigManager

**Use Case:** Store MCPBridge configuration alongside other Team Brain tool
settings in a centralized config store.

**Why:** Consistent configuration management; Logan can change ports/paths
in one place and all tools update.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default MCPBridge config
DEFAULT_MCONFIG = {
    "mcp_port": 8765,
    "a2a_port": 8766,
    "db_path": str(Path.home() / ".mcpbridge" / "registry.db"),
    "log_path": str(Path.home() / ".mcpbridge" / "bridge.log"),
    "auto_register_all": True,
    "verbose": False
}

try:
    from configmanager import ConfigManager
    config = ConfigManager()
    mcp_config = config.get("mcpbridge", DEFAULT_MCONFIG)
    # Save defaults if not set
    config.set("mcpbridge", {**DEFAULT_MCONFIG, **mcp_config})
    config.save()
except ImportError:
    mcp_config = DEFAULT_MCONFIG

# Initialize bridge with config
from mcpbridge import ProtocolBridge, AgentCardGenerator

bridge = ProtocolBridge(
    db_path=Path(mcp_config["db_path"]),
    mcp_port=mcp_config["mcp_port"],
    a2a_port=mcp_config["a2a_port"],
    log_path=Path(mcp_config["log_path"]) if mcp_config.get("log_path") else None,
    verbose=mcp_config.get("verbose", False)
)

# Auto-register if configured
if mcp_config.get("auto_register_all", True):
    for card in AgentCardGenerator.generate_all():
        bridge.registry.register_agent(card)
    print(f"[OK] Auto-registered {len(AgentCardGenerator.generate_all())} agents")

status = bridge.status()
print(f"[OK] MCPBridge configured: MCP:{status['mcp_port']} A2A:{status['a2a_port']}")
```

**Result:** Centralized configuration management for MCPBridge.

---

## Pattern 8: MCPBridge + CollabSession

**Use Case:** Prevent race conditions when multiple agents try to register
or modify the agent registry simultaneously.

**Why:** If ATLAS and FORGE both start at the same time and both run
`register --all`, you might get conflicts. CollabSession prevents this.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge, AgentCardGenerator

try:
    from collabsession import CollabSession
    collab = CollabSession()
    has_collab = True
except ImportError:
    has_collab = False

bridge = ProtocolBridge()
REGISTRY_RESOURCE = "mcpbridge_registry"

if has_collab:
    session_id = collab.start_session(
        "mcpbridge_registration",
        participants=["ATLAS", "FORGE"]
    )
    # Acquire exclusive registry lock
    acquired = collab.lock_resource(session_id, REGISTRY_RESOURCE, "ATLAS")
    if not acquired:
        print("[!] Registry locked by another agent, waiting...")
        import time
        time.sleep(2)
        acquired = collab.lock_resource(session_id, REGISTRY_RESOURCE, "ATLAS")
else:
    acquired = True
    session_id = None

try:
    if acquired:
        # Safe concurrent-free registration
        cards = AgentCardGenerator.generate_all()
        for card in cards:
            bridge.registry.register_agent(card)
        print(f"[OK] Registered {len(cards)} agents (collision-safe)")
    else:
        print("[!] Could not acquire lock, registration skipped")
finally:
    if has_collab and session_id:
        collab.unlock_resource(session_id, REGISTRY_RESOURCE)
        collab.end_session(session_id)
```

**Result:** Safe concurrent agent registration without conflicts.

---

## Pattern 9: Multi-Tool A2A Workflow

**Use Case:** ATLAS delegates a security analysis task to an external agent,
tracks it via TaskQueuePro, records it via SessionReplay, and notifies via SynapseLink.

**Why:** Production-grade A2A delegation with full observability.

```python
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge, STATUS_FAILED, STATUS_COMPLETED

bridge = ProtocolBridge()

# Optional integrations
tools = {}
try:
    from taskqueuepro import TaskQueuePro
    tools["queue"] = TaskQueuePro()
except ImportError:
    pass
try:
    from sessionreplay import SessionReplay
    tools["replay"] = SessionReplay()
except ImportError:
    pass
try:
    from synapselink import quick_send
    tools["synapse"] = quick_send
except ImportError:
    pass

# --- Begin orchestrated A2A delegation ---

agent_url = "http://security-analyzer.example.com"
task_message = "Check Python code for SQL injection: def get(id): return db.execute(f'SELECT * FROM users WHERE id={id}')"

# 1. Create queue entry
queue_id = None
if "queue" in tools:
    queue_id = tools["queue"].create_task("A2A Security Analysis", agent="ATLAS")
    tools["queue"].start_task(queue_id)

# 2. Start session recording
session_id = None
if "replay" in tools:
    session_id = tools["replay"].start_session("ATLAS", task="A2A security analysis")
    tools["replay"].log_input(session_id, f"Target: {agent_url}")
    tools["replay"].log_input(session_id, f"Message: {task_message[:80]}")

try:
    # 3. Discover agent
    card = bridge.discover_external_agent(agent_url)
    if not card:
        raise ValueError(f"Agent not found at {agent_url}")
    
    if "replay" in tools and session_id:
        tools["replay"].log_output(session_id, f"Discovered: {card.name}")
    
    # 4. Delegate task
    task = bridge.delegate_to_external(card.url, task_message)
    
    if "replay" in tools and session_id:
        tools["replay"].log_output(session_id, f"Task {task.task_id}: {task.status}")
    
    # 5. Complete queue entry
    if "queue" in tools and queue_id:
        tools["queue"].complete_task(queue_id, result={"task_id": task.task_id})
    
    # 6. Notify team
    if "synapse" in tools:
        tools["synapse"]("FORGE", "A2A Delegation Complete",
                         f"Task: {task.task_id}\nAgent: {card.name}\nStatus: {task.status}")
    
    # 7. End session recording
    if "replay" in tools and session_id:
        tools["replay"].end_session(session_id, status="COMPLETED")
    
    print(f"[OK] Multi-tool A2A workflow complete: {task.task_id}")

except Exception as e:
    if "queue" in tools and queue_id:
        tools["queue"].fail_task(queue_id, error=str(e))
    if "replay" in tools and session_id:
        tools["replay"].log_error(session_id, str(e))
        tools["replay"].end_session(session_id, status="FAILED")
    if "synapse" in tools:
        tools["synapse"]("FORGE,ATLAS", "A2A Delegation Failed",
                         f"Error: {e}", priority="HIGH")
    print(f"[X] Workflow failed: {e}")
```

**Result:** Fully instrumented A2A delegation with queue tracking, session recording,
and team notifications.

---

## Pattern 10: Full Team Brain Stack

**Use Case:** Complete MCPBridge integration with all Team Brain tools for
production Internet of Agents operation.

**Why:** Production deployment requires health monitoring, task tracking,
session replay, memory persistence, and team notifications working together.

```python
#!/usr/bin/env python3
"""
MCPBridge Full Team Brain Stack Integration
Production-grade MCPBridge deployment with all available tools.
"""
import sys
import time
import signal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpbridge import ProtocolBridge, AgentCardGenerator, MCPTool

# --- Initialize all available Team Brain tools ---
tools_available = {}

def try_import(name, import_func):
    try:
        tools_available[name] = import_func()
        print(f"  [OK] {name} available")
    except ImportError:
        print(f"  [!] {name} not available (optional)")

print("[...] Loading Team Brain tools...")
try_import("config", lambda: __import__("configmanager", fromlist=["ConfigManager"]).ConfigManager())
try_import("health", lambda: __import__("agenthealth", fromlist=["AgentHealth"]).AgentHealth())
try_import("synapse", lambda: __import__("synapselink", fromlist=["quick_send"]).quick_send)
try_import("memory", lambda: __import__("memorybridge", fromlist=["MemoryBridge"]).MemoryBridge())
try_import("replay", lambda: __import__("sessionreplay", fromlist=["SessionReplay"]).SessionReplay())

# --- Configure MCPBridge ---
config = tools_available.get("config")
mcp_config = config.get("mcpbridge", {"mcp_port": 8765, "a2a_port": 8766}) if config else {}

bridge = ProtocolBridge(
    db_path=Path.home() / ".mcpbridge" / "production.db",
    mcp_port=mcp_config.get("mcp_port", 8765),
    a2a_port=mcp_config.get("a2a_port", 8766),
    log_path=Path.home() / ".mcpbridge" / "production.log"
)

# --- Session tracking ---
session_id = None
health = tools_available.get("health")
if health:
    session_id = "mcpbridge_prod_session"
    health.start_session("ATLAS", session_id=session_id, context="MCPBridge full stack")

replay = tools_available.get("replay")
replay_session = None
if replay:
    replay_session = replay.start_session("ATLAS", task="MCPBridge production startup")

# --- Register all BCH agents ---
print("[...] Registering BCH agents...")
cards = AgentCardGenerator.generate_all()
for card in cards:
    bridge.registry.register_agent(card)

# --- Register ATLAS with full tool suite ---
atlas_tools = [
    MCPTool("get_status", "Get Team Brain status summary"),
    MCPTool("list_agents", "List all registered agents"),
    MCPTool("discover_agents", "Discover external A2A agents"),
]
bridge.register_bch_agent("ATLAS", "Team Brain Implementation Lead", tools=atlas_tools)
mcp = bridge.get_mcp_handler("ATLAS")
mcp.register_tool_handler("get_status", lambda a: str(bridge.status()))
mcp.register_tool_handler("list_agents", lambda a: str([c.name for c in bridge.registry.list_agents()]))
mcp.register_tool_handler("discover_agents", lambda a: "Discovering...")

# --- Start servers ---
bridge.start_servers()
status = bridge.status()

if health and session_id:
    health.heartbeat("ATLAS", context=f"MCPBridge serving {status['registered_agents']} agents")
if replay and replay_session:
    replay.log_output(replay_session, f"Servers running: MCP:{status['mcp_port']} A2A:{status['a2a_port']}")

# --- Notify team ---
synapse = tools_available.get("synapse")
if synapse:
    synapse("TEAM",
            "MCPBridge Production Online",
            f"MCP: http://localhost:{status['mcp_port']}/mcp\n"
            f"A2A: http://localhost:{status['a2a_port']}\n"
            f"Agents: {', '.join(status['agent_names'])}\n"
            f"Stack: {', '.join(tools_available.keys())}",
            priority="NORMAL")

print(f"\n[OK] Full Team Brain Stack online")
print(f"     Agents: {status['registered_agents']}")
print(f"     Tools:  {', '.join(tools_available.keys()) or 'standalone'}")
print(f"     MCP:    http://localhost:{status['mcp_port']}/mcp")
print(f"     A2A:    http://localhost:{status['a2a_port']}")
print(f"     Press Ctrl+C to stop")

# --- Graceful shutdown ---
def shutdown(sig, frame):
    print("\n[...] Shutting down...")
    bridge.stop_servers()
    if health and session_id:
        health.end_session("ATLAS", session_id=session_id, status="success")
    if replay and replay_session:
        replay.end_session(replay_session, status="COMPLETED")
    if synapse:
        synapse("TEAM", "MCPBridge Offline", "Servers stopped cleanly.")
    print("[OK] Clean shutdown complete")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

# --- Production loop ---
while True:
    time.sleep(60)
    status = bridge.status()
    if health and session_id:
        health.heartbeat("ATLAS", context=f"MCPBridge: {status['registered_agents']} agents, {status['recent_tasks']} recent tasks")
```

**Result:** Production-grade MCPBridge deployment with full Team Brain observability
stack: health monitoring, task tracking, session recording, memory persistence,
and team notifications.

---

## Troubleshooting Integration Issues

**Import errors:**
```python
# Ensure AutoProjects is in path
import sys
sys.path.insert(0, r"C:\Users\logan\OneDrive\Documents\AutoProjects")
from mcpbridge import ProtocolBridge
```

**Tool version mismatches:**
```bash
# Check each tool
python AutoProjects/MCPBridge/mcpbridge.py --version
python AutoProjects/AgentHealth/agenthealth.py --version
```

**Database conflicts:**
```python
# Use separate databases per environment
from mcpbridge import ProtocolBridge
from pathlib import Path

dev = ProtocolBridge(db_path=Path("~/.mcpbridge/dev.db").expanduser())
prod = ProtocolBridge(db_path=Path("~/.mcpbridge/prod.db").expanduser())
```

---

**Last Updated:** February 21, 2026  
**Maintained By:** ATLAS (Team Brain)  
**For:** Logan Smith / Metaphy LLC
