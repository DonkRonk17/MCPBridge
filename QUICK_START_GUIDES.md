# MCPBridge - Quick Start Guides

**For:** Team Brain Agents (ATLAS, FORGE, CLIO, NEXUS, BOLT)  
**Each guide:** ~5 minutes to complete

## Choose Your Guide:
- [ATLAS (Builder / Implementation Lead)](#atlas-quick-start)
- [FORGE (Orchestrator / Reviewer)](#forge-quick-start)
- [CLIO (Linux / CLI Agent)](#clio-quick-start)
- [NEXUS (Multi-Platform)](#nexus-quick-start)
- [BOLT (Free Executor)](#bolt-quick-start)

---

## ATLAS QUICK START

**Role:** Implementation Lead / Builder  
**Time:** 5 minutes  
**Goal:** Register ATLAS as MCP server so Claude Desktop and Cursor can call your tools

### Step 1: Verify Installation

```bash
cd C:\Users\logan\OneDrive\Documents\AutoProjects\MCPBridge
python mcpbridge.py --version
# Expected: MCPBridge v1.0.0
python test_mcpbridge.py
# Expected: 67/67 tests PASSED
```

### Step 2: Register ATLAS (30 seconds)

```bash
python mcpbridge.py register --agent ATLAS
# [OK] Registered: ATLAS

python mcpbridge.py card --agent ATLAS
# Shows full A2A agent card JSON
```

### Step 3: Start Servers

```bash
python mcpbridge.py serve
# [OK] MCPBridge running
#      MCP server:  http://localhost:8765/mcp
#      A2A server:  http://localhost:8766
```

### Step 4: Verify Your Card is Discoverable

```bash
# In a new terminal:
curl http://localhost:8766/.well-known/agent.json
# Should show ATLAS agent card JSON
```

### Step 5: Integrate in Your Session Scripts

Add to your session startup:
```python
from mcpbridge import ProtocolBridge, MCPTool

bridge = ProtocolBridge()
tools = [
    MCPTool("build_tool", "Build a Python tool following Holy Grail Protocol"),
    MCPTool("run_tests", "Run test suite and report results"),
    MCPTool("check_quality", "Verify all 6 quality gates pass"),
]
bridge.register_bch_agent("ATLAS", "Team Brain Implementation Lead", tools=tools)
mcp = bridge.get_mcp_handler("ATLAS")
mcp.register_tool_handler("build_tool", lambda a: "Build started")
mcp.register_tool_handler("run_tests", lambda a: "Tests running")
mcp.register_tool_handler("check_quality", lambda a: "All gates PASS")
bridge.start_servers()
```

### Next Steps for ATLAS
1. Add MCPBridge startup to your Holy Grail Protocol Phase 0
2. Read [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) - Pattern 9 (multi-tool workflow)
3. Configure Claude Desktop config to use BCH MCP endpoint
4. Use `mcpbridge tasks` to track any delegated work

---

## FORGE QUICK START

**Role:** Orchestrator / Reviewer  
**Time:** 5 minutes  
**Goal:** Discover external agents and orchestrate A2A task delegation

### Step 1: Verify + Register All Agents

```bash
cd C:\Users\logan\OneDrive\Documents\AutoProjects\MCPBridge
python mcpbridge.py register --all
python mcpbridge.py list
# Should show all 5 agents
```

### Step 2: Get Your Agent Card

```bash
python mcpbridge.py card --agent FORGE
```

Review the skills section — these are what external agents will see FORGE can do:
- `forge_review`: Code review and architectural feedback
- `forge_spec`: Technical specification writing

### Step 3: Discover an External Agent

```bash
# Try discovering a test endpoint (if available):
python mcpbridge.py discover --url http://external-agent.example.com
# On failure: "[X] Discovery failed" - normal if no external agent running
```

**Python API for orchestration:**
```python
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()

# In your orchestration logic
for agent_url in external_agent_candidates:
    card = bridge.discover_external_agent(agent_url)
    if card and any(s.get("id") == "code_review" for s in card.skills):
        print(f"Found code reviewer: {card.name}")
        task = bridge.delegate_to_external(card.url, "Review: [code here]")
        print(f"Delegated task: {task.task_id}")
        break
```

### Step 4: Check Task Status

```bash
python mcpbridge.py tasks
# Shows all delegated tasks with status
```

### Step 5: Send Synapse Discovery Report

```python
from synapselink import quick_send
from mcpbridge import ProtocolBridge

bridge = ProtocolBridge()
agents = bridge.registry.list_agents()
external = [a for a in agents if a.provider and "Metaphy" not in a.provider.get("organization", "")]

if external:
    quick_send("TEAM", f"{len(external)} External Agents Available",
               "\n".join(f"- {a.name}: {a.description[:60]}" for a in external))
```

### Next Steps for FORGE
1. Read [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) - Pattern 9 and 10
2. Add MCPBridge discovery to your weekly orchestration review
3. Review INTEGRATION_PLAN.md for adoption roadmap
4. Assign CLIO to test Linux endpoint accessibility

---

## CLIO QUICK START

**Role:** Linux/CLI Agent  
**Time:** 5 minutes  
**Goal:** Set up MCPBridge on Linux/WSL and verify cross-platform operation

### Step 1: Linux Setup

```bash
# On WSL / Ubuntu
cd ~
git clone https://github.com/DonkRonk17/MCPBridge.git
cd MCPBridge

# Verify Python version
python3 --version  # Need 3.8+

# Run tests
python3 test_mcpbridge.py
# Expected: 67/67 PASSED
```

### Step 2: Register and Serve

```bash
# Register all BCH agents
python3 mcpbridge.py register --all \
  --db ~/.mcpbridge/registry.db

# List to verify
python3 mcpbridge.py list --db ~/.mcpbridge/registry.db

# Start servers
python3 mcpbridge.py serve \
  --db ~/.mcpbridge/registry.db \
  --mcp-port 8765 \
  --a2a-port 8766
```

### Step 3: Test Endpoints

```bash
# In another terminal:
curl http://localhost:8765/health
# {"status": "ok", "service": "MCPBridge"}

curl http://localhost:8766/.well-known/agent.json
# ATLAS agent card JSON

curl http://localhost:8766/agents
# All 5 BCH agent cards

# Test MCP initialize
curl -X POST http://localhost:8765/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Step 4: Add to ABIOS Startup

```bash
# Edit ~/.bashrc or CLIO startup script:
echo "# MCPBridge startup" >> ~/.bashrc
echo "python3 ~/MCPBridge/mcpbridge.py register --all --db ~/.mcpbridge/registry.db 2>/dev/null" >> ~/.bashrc
echo "[OK] BCH agents registered in MCPBridge"
```

### Step 5: Run as Background Service

```bash
# Start in background
nohup python3 mcpbridge.py serve \
  --db ~/.mcpbridge/registry.db \
  > ~/.mcpbridge/bridge.log 2>&1 &
echo "MCPBridge PID: $!"

# Check logs
tail -f ~/.mcpbridge/bridge.log
```

### Next Steps for CLIO
1. Report Linux-specific issues to ATLAS via Synapse
2. Test from external WSL2 IP (not just localhost)
3. Verify `chmod +x mcpbridge.py` works on Linux
4. Add to Trophy Room catalog (new tool operational)

---

## NEXUS QUICK START

**Role:** Multi-Platform / VS Code Agent  
**Time:** 5 minutes  
**Goal:** Configure VS Code + MCP and test cross-platform compatibility

### Step 1: Cross-Platform Verification

```python
# Run this to verify cross-platform compatibility
import platform
import sys
sys.path.insert(0, r"C:\Users\logan\OneDrive\Documents\AutoProjects\MCPBridge")

from mcpbridge import ProtocolBridge, AgentCardGenerator

print(f"Platform: {platform.system()} {platform.release()}")
bridge = ProtocolBridge()

# Test all core operations
cards = AgentCardGenerator.generate_all()
print(f"Generated {len(cards)} agent cards")

for card in cards:
    d = card.to_dict()
    assert all(k in d for k in ["name", "url", "skills"])
    print(f"  [OK] {card.name}: A2A card valid")

print("Cross-platform compatibility: PASS")
```

### Step 2: VS Code MCP Integration

If you use VS Code with MCP extension:

```json
// .vscode/settings.json
{
  "mcp.servers": {
    "bch-bridge": {
      "url": "http://localhost:8765/mcp",
      "name": "BCH Agent Bridge"
    }
  }
}
```

Or for continue.dev:
```json
// ~/.continue/config.json
{
  "models": [],
  "contextProviders": [],
  "mcp": {
    "servers": [{
      "name": "BCH Bridge",
      "url": "http://localhost:8765/mcp"
    }]
  }
}
```

### Step 3: Multi-Platform CLI Test

```bash
# Windows PowerShell
python mcpbridge.py register --all
python mcpbridge.py status

# Git Bash on Windows  
python mcpbridge.py serve --verbose &
curl http://localhost:8765/health

# WSL/Linux (same repo via network share)
python3 /mnt/c/Users/logan/OneDrive/Documents/AutoProjects/MCPBridge/mcpbridge.py status
```

### Step 4: Check Cross-Platform Issues

Known platform differences:
- **Windows**: UTF-8 auto-fixed in main() (`sys.stdout.reconfigure`)
- **Linux paths**: Use `Path.home() / ".mcpbridge"` (handled automatically)
- **Port binding**: `0.0.0.0` vs `localhost` — use `--host` flag if needed

```bash
# If binding to all interfaces:
python mcpbridge.py serve --host 0.0.0.0
```

### Next Steps for NEXUS
1. Test MCPBridge on all platforms (Windows, WSL, macOS if available)
2. Document platform-specific issues in a GitHub issue
3. Add MCPBridge to VS Code project templates
4. Test MCP extension compatibility with BCH tools

---

## BOLT QUICK START

**Role:** Free Executor (Cline + Grok)  
**Time:** 5 minutes  
**Goal:** Register BCH agents and run protocol endpoints at zero API cost

### Step 1: Verify (Zero API Cost)

```bash
# All operations below cost $0 in API calls
python mcpbridge.py --version
python test_mcpbridge.py
```

### Step 2: Register and List (Zero Cost)

```bash
python mcpbridge.py register --all
python mcpbridge.py list
python mcpbridge.py status
```

### Step 3: Start Servers (Zero Cost)

```bash
python mcpbridge.py serve
# Keeps running, no API calls made
# External systems can now discover BCH agents for free
```

### Step 4: Check Tasks (Zero Cost)

```bash
python mcpbridge.py tasks
python mcpbridge.py tasks --limit 100
```

### Step 5: Automation Script

```bash
#!/bin/bash
# BOLT: MCPBridge manager (zero API cost)
# Usage: ./bolt_bridge.sh {start|stop|status|register}

BRIDGE_PID_FILE="/tmp/mcpbridge.pid"
MCPBRIDGE="python AutoProjects/MCPBridge/mcpbridge.py"

case "$1" in
  start)
    $MCPBRIDGE register --all
    nohup $MCPBRIDGE serve > /tmp/mcpbridge.log 2>&1 &
    echo $! > $BRIDGE_PID_FILE
    echo "Started MCPBridge (PID: $(cat $BRIDGE_PID_FILE))"
    ;;
  stop)
    if [ -f $BRIDGE_PID_FILE ]; then
      kill $(cat $BRIDGE_PID_FILE) 2>/dev/null
      rm $BRIDGE_PID_FILE
      echo "Stopped MCPBridge"
    fi
    ;;
  status)
    $MCPBRIDGE status
    ;;
  register)
    $MCPBRIDGE register --all
    ;;
  *)
    echo "Usage: $0 {start|stop|status|register}"
    exit 1
esac
```

### Next Steps for BOLT
1. Add bridge start/stop to Cline workflow
2. Use MCPBridge to pre-register agents before sessions
3. Report any issues via Synapse (zero cost to identify, ATLAS fixes)
4. Use `mcpbridge tasks` to monitor any delegated work

---

## Shared Resources (All Agents)

| Resource | Location |
|----------|----------|
| Full Documentation | [README.md](README.md) |
| Usage Examples | [EXAMPLES.md](EXAMPLES.md) |
| Integration Plan | [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) |
| Integration Examples | [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) |
| Cheat Sheet | [CHEAT_SHEET.txt](CHEAT_SHEET.txt) |
| GitHub | https://github.com/DonkRonk17/MCPBridge |
| Issues | https://github.com/DonkRonk17/MCPBridge/issues |

**Need help?**
- Post in THE_SYNAPSE with subject `MCPBridge:` prefix
- Direct message ATLAS (builder and maintainer)
- Open GitHub issue for bugs/feature requests

---

**Last Updated:** February 21, 2026  
**Maintained By:** ATLAS (Team Brain)
