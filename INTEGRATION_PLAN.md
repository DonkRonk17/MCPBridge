# MCPBridge - Integration Plan

**Version:** 1.0  
**Built by:** ATLAS (Team Brain)  
**Date:** February 21, 2026

---

## 🎯 INTEGRATION GOALS

MCPBridge transforms BCH from an isolated communication hub into a globally
discoverable node in the Internet of Agents. This document outlines how MCPBridge
integrates with:

1. **Team Brain agents** (ATLAS, FORGE, CLIO, NEXUS, BOLT)
2. **Existing Team Brain tools** (AgentHealth, SynapseLink, TaskQueuePro, etc.)
3. **BCH (Beacon Command Hub)** — future WebSocket bridge (v1.1)
4. **External AI systems** (Claude Desktop, Google ADK, VS Code MCP, custom agents)
5. **Logan's workflows** — startup automation and daily operations

---

## 📦 BCH INTEGRATION

### Current Status (v1.0)
MCPBridge v1.0 implements protocol layers (MCP + A2A) as a standalone service.
Direct BCH WebSocket bridge is planned for v1.1.

### v1.0 BCH Integration Points
- **Agent Cards**: Auto-generated for all BCH agents (ATLAS, FORGE, CLIO, NEXUS, BOLT)
- **Capability Registry**: BCH agent capabilities stored in SQLite for external discovery
- **A2A Endpoint**: BCH agents discoverable at `http://host:8766/.well-known/agent.json`
- **MCP Server**: BCH tools exposed via JSON-RPC 2.0 at `http://host:8765/mcp`

### v1.1 Planned BCH WebSocket Bridge
```python
# Planned v1.1 architecture
class BCHWebSocketBridge:
    """Connects MCPBridge to live BCH WebSocket for real-time agent communication."""
    
    async def connect_to_bch(self, bch_ws_url: str):
        """Connect to BCH WebSocket and route MCP/A2A messages to live agents."""
        pass
    
    async def relay_mcp_call(self, agent_name: str, tool_name: str, args: dict):
        """Relay an MCP tool call to a live BCH agent via WebSocket."""
        pass
```

### BCH Commands (v1.1 target)
```
@mcpbridge register ATLAS
@mcpbridge status
@mcpbridge discover http://external-agent.com
@mcpbridge delegate ATLAS "Analyze this code..."
```

---

## 🤖 AI AGENT INTEGRATION

### Integration Matrix

| Agent | Use Case | Integration Method | Priority |
|-------|----------|-------------------|----------|
| **ATLAS** | Register self as MCP server; expose build tools | Python API | HIGH |
| **FORGE** | Discover external review/spec agents; orchestrate A2A delegation | Python API + CLI | HIGH |
| **CLIO** | Register BCH agents from Linux; test MCP endpoints | CLI | MEDIUM |
| **NEXUS** | Cross-platform testing; VS Code MCP integration | CLI + config | MEDIUM |
| **BOLT** | Register agents, serve endpoints for external callers | CLI | LOW |

### Agent-Specific Workflows

#### ATLAS (Implementation Lead / Builder)
**Primary Use Case:** Register ATLAS as MCP server so Claude Desktop / Cursor IDE
can call ATLAS's building capabilities directly.

**Integration Steps:**
1. Add `mcpbridge register --agent ATLAS` to ATLAS session startup
2. Register custom MCP tools (build_tool, run_tests, check_quality)
3. Wire handlers to actual ATLAS functions
4. Add to Claude Desktop MCP config

**Session Startup Code:**
```python
from mcpbridge import ProtocolBridge, MCPTool
from pathlib import Path

# ATLAS session start
bridge = ProtocolBridge(
    db_path=Path("D:/BEACON_HQ/mcpbridge.db"),
    log_path=Path("D:/BEACON_HQ/mcpbridge.log")
)

# Register ATLAS with Holy Grail tools
atlas_tools = [
    MCPTool("build_tool", "Build Python tool following Holy Grail Protocol"),
    MCPTool("run_test_suite", "Run test suite and return pass/fail counts"),
    MCPTool("check_quality_gates", "Verify all 6 quality gates pass"),
    MCPTool("update_manifest", "Update PROJECT_MANIFEST.md with new tool"),
]

card = bridge.register_bch_agent("ATLAS", "Implementation Lead", tools=atlas_tools)
mcp = bridge.get_mcp_handler("ATLAS")

# Wire to actual ATLAS functions
mcp.register_tool_handler("build_tool", lambda a: build_tool_handler(a))
mcp.register_tool_handler("run_test_suite", lambda a: run_tests_handler(a))
mcp.register_tool_handler("check_quality_gates", lambda a: quality_check_handler(a))
mcp.register_tool_handler("update_manifest", lambda a: update_manifest_handler(a))
```

**Use in ATLAS Tool Building:**
```bash
# At session start
python mcpbridge.py register --agent ATLAS
# ATLAS is now discoverable as A2A agent AND usable via MCP
```

---

#### FORGE (Orchestrator / Reviewer)
**Primary Use Case:** Discover and delegate to specialized external review agents.
Forge orchestrates multi-agent workflows across BCH and external systems.

**Integration Steps:**
1. Use MCPBridge to discover external code review and spec-writing agents
2. Delegate complex analysis tasks to specialized external agents
3. Aggregate results and route back through BCH

**Forge Orchestration Pattern:**
```python
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()

# Discover specialized agents
code_reviewer = bridge.discover_external_agent("http://code-review-ai.example.com")
research_agent = bridge.discover_external_agent("http://research-ai.example.com")

# Delegate parallel tasks
review_task = bridge.delegate_to_external(
    code_reviewer.url,
    "Review this architecture for ATLAS's new tool..."
)
research_task = bridge.delegate_to_external(
    research_agent.url, 
    "Research best practices for MCP server implementation..."
)

# FORGE aggregates and routes back to BCH
```

**Synapse Notification after Discovery:**
```python
from synapselink import quick_send
if card := bridge.discover_external_agent(url):
    quick_send("TEAM", f"New Capability: {card.name}",
               f"{card.description}\nSkills: {[s['id'] for s in card.skills]}")
```

---

#### CLIO (Linux / CLI Agent)
**Primary Use Case:** Run MCPBridge on Linux (Ubuntu/WSL) to expose BCH to
Linux-based external agents and test MCP endpoints.

**Integration Steps:**
1. Clone MCPBridge to WSL/Ubuntu environment
2. Register all BCH agents for Linux-side exposure
3. Test MCP endpoint reachability

**Linux Setup:**
```bash
# On WSL / Ubuntu CLIO
git clone https://github.com/DonkRonk17/MCPBridge.git
cd MCPBridge

# Register all agents
python3 mcpbridge.py register --all

# Start with Linux-appropriate paths
python3 mcpbridge.py serve \
  --db ~/.mcpbridge/registry.db \
  --mcp-port 8765 \
  --a2a-port 8766

# Test endpoint
curl http://localhost:8765/health
curl http://localhost:8766/.well-known/agent.json
```

**ABIOS Integration:**
```bash
# Add to CLIO's ABIOS startup script
python3 ~/AutoProjects/MCPBridge/mcpbridge.py register --all --quiet
echo "[MCPBridge] BCH agents registered for A2A discovery"
```

---

#### NEXUS (Multi-Platform / VS Code)
**Primary Use Case:** Configure VS Code to use BCH tools via MCP extension.
Test cross-platform compatibility of MCPBridge endpoints.

**VS Code MCP Extension Config:**
```json
// .vscode/settings.json
{
  "mcp.servers": {
    "bch-nexus": {
      "url": "http://localhost:8765/mcp",
      "name": "BCH Agent Bridge"
    }
  }
}
```

**Cross-Platform Testing:**
```python
import platform
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()
print(f"Platform: {platform.system()}")

# Test registration works on all platforms
cards = []
for name in ["ATLAS", "FORGE", "CLIO"]:
    card = bridge.register_bch_agent(name, f"{name} agent")
    cards.append(card)

print(f"Registered {len(cards)} agents on {platform.system()}")

# Verify agent cards have correct format
for card in cards:
    d = card.to_dict()
    assert "name" in d and "url" in d and "skills" in d
    print(f"  {card.name}: A2A card valid")
```

---

#### BOLT (Free Executor / Cline+Grok)
**Primary Use Case:** Run MCPBridge registration and serving without requiring
expensive API calls. All MCPBridge operations are local, zero API cost.

**Cost-Free Operations:**
```bash
# All these operations cost $0 in API calls
python mcpbridge.py register --all      # Register BCH agents
python mcpbridge.py serve               # Serve MCP/A2A endpoints
python mcpbridge.py tasks              # Check task history
python mcpbridge.py status             # Get bridge status
python mcpbridge.py list               # List agents
```

**BOLT Automation Script:**
```bash
#!/bin/bash
# BOLT: Wake BCH Internet of Agents bridge
echo "Starting MCPBridge..."
python AutoProjects/MCPBridge/mcpbridge.py register --all --db ~/.mcpbridge/bolt.db
python AutoProjects/MCPBridge/mcpbridge.py serve \
  --db ~/.mcpbridge/bolt.db \
  --mcp-port 8765 \
  --a2a-port 8766 &
echo "MCPBridge started (PID: $!)"
```

---

## 🔗 INTEGRATION WITH OTHER TEAM BRAIN TOOLS

### With AgentHealth
**Use Case:** Correlate MCPBridge protocol activity with agent health monitoring.

```python
from agenthealth import AgentHealth
from mcpbridge import ProtocolBridge

health = AgentHealth()
bridge = ProtocolBridge()

session_id = "mcpbridge_session_001"
health.start_session("ATLAS", session_id=session_id, context="MCPBridge active")

try:
    bridge.register_bch_agent("ATLAS", "Implementation Lead")
    bridge.start_servers()
    health.heartbeat("ATLAS", context="MCP+A2A servers running")
    
    # ... do work ...
    
    health.end_session("ATLAS", session_id=session_id, status="success")
except Exception as e:
    health.log_error("ATLAS", f"MCPBridge error: {e}")
    health.end_session("ATLAS", session_id=session_id, status="failed")
```

---

### With SynapseLink
**Use Case:** Notify Team Brain when new external agents are discovered
or major protocol events occur.

```python
from synapselink import quick_send
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()

# Notify on new agent discovery
card = bridge.discover_external_agent(url)
if card:
    quick_send(
        "TEAM",
        f"New External Agent Discovered: {card.name}",
        f"Description: {card.description}\n"
        f"URL: {card.url}\n"
        f"Skills: {len(card.skills)}\n"
        f"Registered in MCPBridge registry for delegation.",
        priority="NORMAL"
    )

# Notify FORGE when A2A task delegation completes
task = bridge.delegate_to_external(url, message)
if task.status == "completed":
    quick_send("FORGE", f"External Task Complete: {task.task_id}",
               f"Result: {task.result}")
elif task.status == "failed":
    quick_send("FORGE,LOGAN", "External Task Failed",
               f"Error: {task.error}", priority="HIGH")
```

---

### With TaskQueuePro
**Use Case:** Track A2A delegations alongside BCH internal tasks for
unified workflow visibility.

```python
from taskqueuepro import TaskQueuePro
from mcpbridge import ProtocolBridge

queue = TaskQueuePro()
bridge = ProtocolBridge()

# Create queue entry for the delegation
queue_task_id = queue.create_task(
    title="A2A: Code review by ExternalAgent",
    agent="ATLAS",
    priority=2,
    metadata={"type": "a2a_delegation", "target_agent": "ExternalAgent"}
)
queue.start_task(queue_task_id)

try:
    # Delegate via A2A
    a2a_task = bridge.delegate_to_external(url, message)
    
    # Complete queue entry
    queue.complete_task(queue_task_id, result={"a2a_task_id": a2a_task.task_id})
except Exception as e:
    queue.fail_task(queue_task_id, error=str(e))
```

---

### With SessionReplay
**Use Case:** Record MCPBridge sessions for debugging protocol issues.

```python
from sessionreplay import SessionReplay
from mcpbridge import ProtocolBridge

replay = SessionReplay()
bridge = ProtocolBridge()

session_id = replay.start_session("ATLAS", task="A2A agent discovery")

try:
    replay.log_input(session_id, f"Discovering: {url}")
    card = bridge.discover_external_agent(url)
    
    if card:
        replay.log_output(session_id, f"Found: {card.name} ({len(card.skills)} skills)")
        task = bridge.delegate_to_external(card.url, "Test task")
        replay.log_output(session_id, f"Task {task.task_id}: {task.status}")
        replay.end_session(session_id, status="COMPLETED")
    else:
        replay.log_output(session_id, "Discovery failed")
        replay.end_session(session_id, status="PARTIAL")
        
except Exception as e:
    replay.log_error(session_id, str(e))
    replay.end_session(session_id, status="FAILED")
```

---

### With MemoryBridge
**Use Case:** Persist discovered external agents to memory core for
cross-session availability.

```python
from memorybridge import MemoryBridge
from mcpbridge import ProtocolBridge

memory = MemoryBridge()
bridge = ProtocolBridge()

# Load previously discovered agents
known_agents = memory.get("mcpbridge_external_agents", default=[])

# Discover new agents
for url in agent_urls:
    card = bridge.discover_external_agent(url)
    if card:
        known_agents.append({"name": card.name, "url": card.url, "discovered": "2026-02-21"})

# Persist for future sessions
memory.set("mcpbridge_external_agents", known_agents)
memory.sync()
```

---

### With ConfigManager
**Use Case:** Centralize MCPBridge configuration alongside other tools.

```python
from configmanager import ConfigManager
from mcpbridge import ProtocolBridge
from pathlib import Path

config = ConfigManager()

# Load MCPBridge config from central store
mcp_config = config.get("mcpbridge", {
    "mcp_port": 8765,
    "a2a_port": 8766,
    "db_path": "~/.mcpbridge/registry.db",
    "auto_register_all": True
})

bridge = ProtocolBridge(
    db_path=Path(mcp_config["db_path"]).expanduser(),
    mcp_port=mcp_config["mcp_port"],
    a2a_port=mcp_config["a2a_port"]
)

if mcp_config.get("auto_register_all"):
    from mcpbridge import AgentCardGenerator
    for card in AgentCardGenerator.generate_all():
        bridge.registry.register_agent(card)
```

---

### With ContextCompressor
**Use Case:** Compress large agent card catalogs before sharing in Synapse.

```python
from contextcompressor import ContextCompressor
from mcpbridge import ProtocolBridge
import json

compressor = ContextCompressor()
bridge = ProtocolBridge()

# Generate full agent catalog
agents = bridge.registry.list_agents()
catalog = json.dumps([a.to_dict() for a in agents], indent=2)

# Compress for Synapse sharing
compressed = compressor.compress_text(
    catalog,
    query="agent capabilities and skills",
    method="summary"
)

print(f"Full catalog: {len(catalog)} chars")
print(f"Compressed: {len(compressed.compressed_text)} chars")
```

---

### With CollabSession
**Use Case:** Prevent conflicts when multiple agents discover/register
at the same time.

```python
from collabsession import CollabSession
from mcpbridge import ProtocolBridge

collab = CollabSession()
bridge = ProtocolBridge()

session_id = collab.start_session("mcpbridge_ops", participants=["ATLAS", "FORGE"])
collab.lock_resource(session_id, "mcpbridge_registry", "ATLAS")

try:
    # Safe to register without conflicts
    from mcpbridge import AgentCardGenerator
    for card in AgentCardGenerator.generate_all():
        bridge.registry.register_agent(card)
finally:
    collab.unlock_resource(session_id, "mcpbridge_registry")
    collab.end_session(session_id)
```

---

## 🚀 ADOPTION ROADMAP

### Phase 1: Core Adoption (Week 1 - Feb 2026)
**Goal:** All BCH agents discoverable, Claude Desktop connected

**Steps:**
1. [x] MCPBridge deployed to GitHub
2. [ ] All agents register via `mcpbridge register --all`
3. [ ] Claude Desktop config updated with MCPBridge MCP server
4. [ ] A2A endpoint tested from external tool
5. [ ] Send Synapse announcement

**Success Criteria:**
- 5/5 BCH agents registered and listed via `mcpbridge list`
- Claude Desktop can list BCH MCP tools
- `/.well-known/agent.json` accessible

---

### Phase 2: Active Integration (Week 2-3)
**Goal:** Agents use MCPBridge daily for external collaboration

**Steps:**
1. [ ] ATLAS registers with custom build tools MCP handler
2. [ ] FORGE discovers and tests external code review agents
3. [ ] Add MCPBridge to Team Brain startup sequence
4. [ ] Task delegation tested end-to-end

**Success Criteria:**
- At least one successful A2A delegation per day
- MCPBridge referenced in at least 3 agent session logs

---

### Phase 3: BCH WebSocket Bridge (Month 2 - v1.1)
**Goal:** Live BCH agent communication via MCP/A2A

**Steps:**
1. [ ] Implement BCHWebSocketBridge class
2. [ ] Route MCP tool calls to live BCH WebSocket
3. [ ] Test real-time bidirectional protocol relay
4. [ ] Update all agent registrations with live handlers

**Success Criteria:**
- MCP tool call → BCH WebSocket → live agent response
- Sub-100ms relay latency on local network

---

## 📊 SUCCESS METRICS

**Adoption Metrics:**
- Agents using MCPBridge: Target 5/5
- External agents discovered: Track weekly
- MCP calls per day: Target 10+
- A2A delegations per week: Target 5+

**Technical Metrics:**
- MCP request latency: < 10ms (local)
- A2A discovery time: < 500ms (network)
- Registry lookup: < 1ms
- Test suite pass rate: 100% (67/67)

**Business Value:**
- External AI capabilities accessible to BCH: Quantifiable
- Time saved vs. custom integration: Hours per integration
- Ecosystem connectivity: First-class MCP/A2A citizen

---

## 🛠️ TECHNICAL INTEGRATION DETAILS

### Import Paths
```python
# Standard imports
from mcpbridge import ProtocolBridge, AgentCard, MCPTool
from mcpbridge import AgentCardGenerator, CapabilityRegistry
from mcpbridge import A2AClientModule, MCPProtocol, MCPStdioAdapter
from mcpbridge import A2ATask, MCPResource, MCPPrompt, MCPError
from mcpbridge import VERSION, DEFAULT_MCP_PORT, DEFAULT_A2A_PORT
from mcpbridge import STATUS_PENDING, STATUS_COMPLETED, STATUS_FAILED
```

### Database Schema (for direct queries)
```sql
-- agents table
SELECT agent_name, registered_at, last_seen FROM agent_cards;

-- tools table  
SELECT agent_name, tool_name FROM mcp_tools;

-- tasks table
SELECT task_id, agent_name, status, created_at FROM task_log
WHERE status != 'completed' ORDER BY created_at DESC;
```

### Error Handling Standards
```python
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()
try:
    card = bridge.discover_external_agent(url)
except Exception as e:
    # MCPBridge never raises on discovery failure - always returns None
    # Only ProtocolBridge.start_servers() can raise (port conflict)
    print(f"Unexpected error: {e}")
```

---

## 🔧 MAINTENANCE & SUPPORT

### Update Strategy
- **v1.0.x**: Bug fixes, no API changes
- **v1.1**: BCH WebSocket bridge (major feature)
- **v2.0**: Streaming support, authentication, TLS

### Known Limitations (v1.0)
1. **No live BCH WebSocket** — Tool handlers are user-defined Python functions,
   not automatically wired to live BCH agents. Planned for v1.1.
2. **No streaming** — MCP streaming (SSE) not yet implemented. Planned v1.1.
3. **No authentication** — A2A runs unauthenticated locally. For production
   external deployment, add reverse proxy with auth.
4. **Single MCP server per HTTP server** — Multiple agents share one MCP HTTP
   endpoint. Each agent needs its own server instance for full isolation.

### Support Channels
- GitHub Issues: Bug reports and feature requests
- Synapse: Team Brain internal discussions
- Direct to ATLAS: Complex protocol questions

---

## 📚 ADDITIONAL RESOURCES

- Main Documentation: [README.md](README.md)
- Examples: [EXAMPLES.md](EXAMPLES.md)
- Quick Start Guides: [QUICK_START_GUIDES.md](QUICK_START_GUIDES.md)
- Integration Examples: [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md)
- GitHub: https://github.com/DonkRonk17/MCPBridge
- MCP Spec: https://modelcontextprotocol.io/specification
- A2A Spec: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/

---

**Last Updated:** February 21, 2026  
**Maintained By:** ATLAS (Team Brain)  
**For:** Logan Smith / Metaphy LLC
