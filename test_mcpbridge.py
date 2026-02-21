#!/usr/bin/env python3
"""
Comprehensive test suite for MCPBridge.

Tests cover:
- AgentCard data class (serialization, factory methods)
- MCPTool, MCPResource, MCPPrompt data classes
- CapabilityRegistry (CRUD, persistence)
- MCPProtocol (all JSON-RPC methods, error handling)
- A2AClientModule (discovery, delegation, polling)
- ProtocolBridge (registration, server lifecycle, status)
- AgentCardGenerator (all BCH agents)
- MCPStdioAdapter (message processing)
- Edge cases and error conditions

Run: python test_mcpbridge.py

Author: ATLAS (Team Brain)
Date: February 21, 2026
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Ensure mcpbridge is importable from same directory
sys.path.insert(0, str(Path(__file__).parent))

from mcpbridge import (
    AgentCard,
    AgentCardGenerator,
    A2AClientModule,
    A2ATask,
    CapabilityRegistry,
    MCPError,
    MCPPrompt,
    MCPProtocol,
    MCPResource,
    MCPStdioAdapter,
    MCPTool,
    ProtocolBridge,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    VERSION,
    DEFAULT_MCP_PORT,
    DEFAULT_A2A_PORT,
)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def make_jsonrpc(method: str, params: dict = None, msg_id: int = 1) -> str:
    """Build a JSON-RPC 2.0 request string."""
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


def make_notification(method: str, params: dict = None) -> str:
    """Build a JSON-RPC 2.0 notification (no id)."""
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


def temp_db() -> Path:
    """Return a temporary database path."""
    tmpdir = tempfile.mkdtemp()
    return Path(tmpdir) / "test_registry.db"


# ---------------------------------------------------------------------------
# Test Suite: AgentCard
# ---------------------------------------------------------------------------

class TestAgentCard(unittest.TestCase):
    """Tests for AgentCard data class."""

    def test_basic_construction(self):
        """AgentCard can be constructed with required fields."""
        card = AgentCard(
            name="TestAgent",
            description="A test agent",
            url="http://localhost:8766/agents/testagent"
        )
        self.assertEqual(card.name, "TestAgent")
        self.assertEqual(card.description, "A test agent")
        self.assertIsNotNone(card.url)

    def test_to_dict_required_fields(self):
        """to_dict() includes all required A2A fields."""
        card = AgentCard(
            name="ATLAS",
            description="Builder",
            url="http://localhost:8766/agents/atlas"
        )
        d = card.to_dict()
        required_keys = [
            "name", "description", "url", "version",
            "capabilities", "skills", "defaultInputModes",
            "defaultOutputModes", "authentication"
        ]
        for key in required_keys:
            self.assertIn(key, d, f"Missing key: {key}")

    def test_from_dict_roundtrip(self):
        """Card serializes to dict and deserializes back correctly."""
        original = AgentCard(
            name="FORGE",
            description="Orchestrator",
            url="http://localhost:8766/agents/forge",
            version="2.0.0",
            skills=[{"id": "spec_write", "name": "Write Spec"}]
        )
        d = original.to_dict()
        restored = AgentCard.from_dict(d)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.description, original.description)
        self.assertEqual(restored.version, original.version)
        self.assertEqual(len(restored.skills), len(original.skills))

    def test_for_bch_agent_factory(self):
        """for_bch_agent() factory produces valid card."""
        card = AgentCard.for_bch_agent(
            agent_name="ATLAS",
            agent_description="Implementation Lead",
            host="localhost",
            port=8766
        )
        self.assertEqual(card.name, "ATLAS")
        self.assertIn("localhost", card.url)
        self.assertIn("8766", card.url)
        self.assertIn("atlas", card.url)
        self.assertTrue(len(card.skills) > 0)
        self.assertIsNotNone(card.provider)

    def test_provider_included_when_set(self):
        """Provider field is included in dict when set."""
        card = AgentCard(
            name="X",
            description="Y",
            url="http://x",
            provider={"organization": "Metaphy LLC"}
        )
        d = card.to_dict()
        self.assertIn("provider", d)
        self.assertEqual(d["provider"]["organization"], "Metaphy LLC")

    def test_from_dict_defaults(self):
        """from_dict() handles missing optional fields with defaults."""
        minimal = {"name": "Agent", "description": "Test", "url": "http://a"}
        card = AgentCard.from_dict(minimal)
        self.assertEqual(card.version, "1.0.0")
        self.assertIsInstance(card.capabilities, dict)
        self.assertIsInstance(card.skills, list)


# ---------------------------------------------------------------------------
# Test Suite: MCPTool / MCPResource / MCPPrompt
# ---------------------------------------------------------------------------

class TestMCPDataClasses(unittest.TestCase):
    """Tests for MCP protocol data classes."""

    def test_mcp_tool_to_mcp_dict(self):
        """MCPTool serializes to correct MCP format."""
        tool = MCPTool(
            name="ping",
            description="Ping an agent",
            input_schema={
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "required": ["target"]
            }
        )
        d = tool.to_mcp_dict()
        self.assertEqual(d["name"], "ping")
        self.assertEqual(d["description"], "Ping an agent")
        self.assertIn("inputSchema", d)
        self.assertEqual(d["inputSchema"]["type"], "object")

    def test_mcp_tool_default_schema(self):
        """MCPTool generates default empty schema when none provided."""
        tool = MCPTool(name="noop", description="Does nothing")
        d = tool.to_mcp_dict()
        self.assertIn("inputSchema", d)
        self.assertEqual(d["inputSchema"]["type"], "object")

    def test_mcp_resource_to_mcp_dict(self):
        """MCPResource serializes to correct MCP format."""
        resource = MCPResource(
            uri="bch://atlas/status",
            name="ATLAS Status",
            description="Current ATLAS status",
            mime_type="application/json"
        )
        d = resource.to_mcp_dict()
        self.assertEqual(d["uri"], "bch://atlas/status")
        self.assertEqual(d["mimeType"], "application/json")
        self.assertIn("description", d)

    def test_mcp_prompt_to_mcp_dict(self):
        """MCPPrompt serializes to correct MCP format."""
        prompt = MCPPrompt(
            name="task_summary",
            description="Summarize a task result",
            arguments=[{"name": "result", "description": "Task result", "required": True}]
        )
        d = prompt.to_mcp_dict()
        self.assertEqual(d["name"], "task_summary")
        self.assertEqual(len(d["arguments"]), 1)


# ---------------------------------------------------------------------------
# Test Suite: CapabilityRegistry
# ---------------------------------------------------------------------------

class TestCapabilityRegistry(unittest.TestCase):
    """Tests for SQLite capability registry."""

    def setUp(self):
        """Create fresh temp database for each test."""
        self.db_path = temp_db()
        self.registry = CapabilityRegistry(self.db_path)

    def test_register_and_get_agent(self):
        """Register an agent and retrieve it by name."""
        card = AgentCard.for_bch_agent("ATLAS", "Builder", "localhost", 8766)
        self.registry.register_agent(card)
        retrieved = self.registry.get_agent("ATLAS")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "ATLAS")

    def test_get_nonexistent_agent_returns_none(self):
        """get_agent() returns None for unknown agent."""
        result = self.registry.get_agent("NONEXISTENT")
        self.assertIsNone(result)

    def test_list_agents_empty(self):
        """list_agents() returns empty list on fresh database."""
        agents = self.registry.list_agents()
        self.assertEqual(agents, [])

    def test_list_agents_multiple(self):
        """list_agents() returns all registered agents."""
        for name in ["ATLAS", "FORGE", "CLIO"]:
            card = AgentCard.for_bch_agent(name, f"{name} agent", "localhost", 8766)
            self.registry.register_agent(card)
        agents = self.registry.list_agents()
        self.assertEqual(len(agents), 3)
        names = {a.name for a in agents}
        self.assertEqual(names, {"ATLAS", "FORGE", "CLIO"})

    def test_register_agent_updates_on_duplicate(self):
        """Re-registering same agent updates without duplicating."""
        card = AgentCard.for_bch_agent("ATLAS", "Builder v1", "localhost", 8766)
        self.registry.register_agent(card)

        card2 = AgentCard.for_bch_agent("ATLAS", "Builder v2", "localhost", 8766)
        self.registry.register_agent(card2)

        agents = self.registry.list_agents()
        self.assertEqual(len(agents), 1)
        self.assertIn("v2", agents[0].description)

    def test_remove_agent(self):
        """remove_agent() deletes the agent and returns True."""
        card = AgentCard.for_bch_agent("BOLT", "Executor", "localhost", 8766)
        self.registry.register_agent(card)
        result = self.registry.remove_agent("BOLT")
        self.assertTrue(result)
        self.assertIsNone(self.registry.get_agent("BOLT"))

    def test_remove_nonexistent_agent_returns_false(self):
        """remove_agent() returns False when agent not found."""
        result = self.registry.remove_agent("GHOST")
        self.assertFalse(result)

    def test_register_and_get_tool(self):
        """Register a tool and retrieve tools for agent."""
        tool = MCPTool(name="ping", description="Ping agent")
        self.registry.register_tool("ATLAS", tool)
        tools = self.registry.get_tools_for_agent("ATLAS")
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "ping")

    def test_get_tools_empty(self):
        """get_tools_for_agent() returns empty for unknown agent."""
        tools = self.registry.get_tools_for_agent("NOBODY")
        self.assertEqual(tools, [])

    def test_log_and_get_task(self):
        """Log a task and retrieve it by ID."""
        task = A2ATask(
            task_id="task-001",
            agent_name="ATLAS",
            message="Build something",
            status=STATUS_PENDING
        )
        self.registry.log_task(task)
        retrieved = self.registry.get_task("task-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.task_id, "task-001")
        self.assertEqual(retrieved.status, STATUS_PENDING)

    def test_list_tasks(self):
        """list_tasks() returns logged tasks, newest first."""
        for i in range(3):
            task = A2ATask(
                task_id=f"task-{i}",
                agent_name="FORGE",
                message=f"Task {i}",
                status=STATUS_COMPLETED
            )
            self.registry.log_task(task)

        tasks = self.registry.list_tasks(limit=10)
        self.assertEqual(len(tasks), 3)

    def test_list_tasks_filter_by_agent(self):
        """list_tasks() filters by agent name when specified."""
        for agent, count in [("ATLAS", 2), ("FORGE", 1)]:
            for i in range(count):
                task = A2ATask(
                    task_id=str(uuid.uuid4()),
                    agent_name=agent,
                    message="work",
                    status=STATUS_COMPLETED
                )
                self.registry.log_task(task)

        atlas_tasks = self.registry.list_tasks(agent_name="ATLAS")
        self.assertEqual(len(atlas_tasks), 2)


# ---------------------------------------------------------------------------
# Test Suite: MCPProtocol
# ---------------------------------------------------------------------------

class TestMCPProtocol(unittest.TestCase):
    """Tests for MCP JSON-RPC protocol handler."""

    def setUp(self):
        """Create protocol with test tools."""
        self.tool = MCPTool(
            name="get_status",
            description="Get agent status",
            input_schema={"type": "object", "properties": {}}
        )
        self.resource = MCPResource(
            uri="bch://atlas/config",
            name="Config",
            description="Agent config"
        )
        self.prompt = MCPPrompt(
            name="summarize",
            description="Summarize results"
        )
        self.proto = MCPProtocol(
            server_name="TestServer",
            server_version="1.0",
            tools=[self.tool],
            resources=[self.resource],
            prompts=[self.prompt]
        )
        self.proto.register_tool_handler("get_status", lambda args: "running")
        self.proto.register_resource_handler(
            "bch://atlas/config", lambda: '{"mode": "test"}'
        )
        self.proto.register_prompt_handler(
            "summarize",
            lambda args: [{"role": "user", "content": {"type": "text", "text": "Summary"}}]
        )

    def test_initialize_returns_protocol_version(self):
        """initialize returns correct protocol version."""
        req = make_jsonrpc(
            "initialize",
            {"clientInfo": {"name": "TestClient", "version": "1.0"}}
        )
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["protocolVersion"], MCPProtocol.PROTOCOL_VERSION)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "TestServer")

    def test_tools_list_returns_tools(self):
        """tools/list returns registered tools."""
        req = make_jsonrpc("tools/list", {})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("result", resp)
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "get_status")

    def test_tools_call_returns_result(self):
        """tools/call invokes handler and returns result."""
        req = make_jsonrpc("tools/call", {"name": "get_status", "arguments": {}})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("result", resp)
        content = resp["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertIn("running", content[0]["text"])

    def test_tools_call_unknown_tool_returns_error(self):
        """tools/call with unknown tool name returns error."""
        req = make_jsonrpc("tools/call", {"name": "nonexistent_tool"})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)

    def test_resources_list_returns_resources(self):
        """resources/list returns registered resources."""
        req = make_jsonrpc("resources/list", {})
        resp = json.loads(self.proto.handle_request(req))
        self.assertEqual(len(resp["result"]["resources"]), 1)
        self.assertEqual(resp["result"]["resources"][0]["uri"], "bch://atlas/config")

    def test_resources_read_returns_content(self):
        """resources/read invokes handler and returns content."""
        req = make_jsonrpc("resources/read", {"uri": "bch://atlas/config"})
        resp = json.loads(self.proto.handle_request(req))
        contents = resp["result"]["contents"]
        self.assertEqual(len(contents), 1)
        self.assertIn("mode", contents[0]["text"])

    def test_resources_read_unknown_uri_returns_error(self):
        """resources/read with unknown URI returns error."""
        req = make_jsonrpc("resources/read", {"uri": "bch://unknown/x"})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("error", resp)

    def test_prompts_list_returns_prompts(self):
        """prompts/list returns registered prompts."""
        req = make_jsonrpc("prompts/list", {})
        resp = json.loads(self.proto.handle_request(req))
        self.assertEqual(len(resp["result"]["prompts"]), 1)

    def test_prompts_get_returns_messages(self):
        """prompts/get invokes handler and returns messages."""
        req = make_jsonrpc("prompts/get", {"name": "summarize", "arguments": {}})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("messages", resp["result"])
        self.assertEqual(len(resp["result"]["messages"]), 1)

    def test_notification_returns_none(self):
        """Notifications (no id) return None."""
        notif = make_notification("notifications/initialized")
        result = self.proto.handle_request(notif)
        self.assertIsNone(result)

    def test_unknown_method_returns_error(self):
        """Calling unknown method returns method-not-found error."""
        req = make_jsonrpc("mystery/method", {})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_invalid_json_returns_parse_error(self):
        """Invalid JSON returns parse error."""
        resp = json.loads(self.proto.handle_request("not valid json {"))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32700)

    def test_tools_call_missing_name_returns_error(self):
        """tools/call without name param returns invalid-params error."""
        req = make_jsonrpc("tools/call", {})
        resp = json.loads(self.proto.handle_request(req))
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)


# ---------------------------------------------------------------------------
# Test Suite: A2ATask
# ---------------------------------------------------------------------------

class TestA2ATask(unittest.TestCase):
    """Tests for A2ATask data class."""

    def test_default_status_is_pending(self):
        """New task has PENDING status by default."""
        task = A2ATask(task_id="t1", agent_name="ATLAS", message="work")
        self.assertEqual(task.status, STATUS_PENDING)

    def test_to_dict_includes_required_fields(self):
        """to_dict() includes all A2A task fields."""
        task = A2ATask(task_id="t1", agent_name="ATLAS", message="work",
                       status=STATUS_COMPLETED, result="done")
        d = task.to_dict()
        self.assertIn("id", d)
        self.assertIn("status", d)
        self.assertIn("agentName", d)
        self.assertEqual(d["status"]["state"], STATUS_COMPLETED)
        self.assertEqual(d["result"], "done")


# ---------------------------------------------------------------------------
# Test Suite: A2AClientModule
# ---------------------------------------------------------------------------

class TestA2AClientModule(unittest.TestCase):
    """Tests for A2A client discovery and delegation."""

    def setUp(self):
        """Create A2A client for tests."""
        self.client = A2AClientModule(timeout=5)

    @patch("urllib.request.urlopen")
    def test_discover_agent_success(self, mock_urlopen):
        """discover_agent() returns AgentCard on success."""
        card_data = {
            "name": "ExternalAgent",
            "description": "Test external agent",
            "url": "http://external.example.com",
            "version": "1.0.0",
            "capabilities": {},
            "skills": [],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "authentication": {"schemes": ["none"]}
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(card_data).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        card = self.client.discover_agent("http://external.example.com")
        self.assertIsNotNone(card)
        self.assertEqual(card.name, "ExternalAgent")

    @patch("urllib.request.urlopen")
    def test_discover_agent_network_error(self, mock_urlopen):
        """discover_agent() returns None on network error."""
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        card = self.client.discover_agent("http://unreachable.example.com")
        self.assertIsNone(card)

    @patch("urllib.request.urlopen")
    def test_discover_agent_invalid_json(self, mock_urlopen):
        """discover_agent() returns None when response is invalid JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        card = self.client.discover_agent("http://bad.example.com")
        self.assertIsNone(card)

    @patch("urllib.request.urlopen")
    def test_delegate_task_success(self, mock_urlopen):
        """delegate_task() returns task with status from server response."""
        task_response = {
            "id": "task-abc",
            "status": {"state": STATUS_PENDING},
            "agentName": "ExternalAgent",
            "message": "Do work",
            "createdAt": "2026-02-21T00:00:00+00:00"
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(task_response).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        task = self.client.delegate_task(
            "http://agent.example.com", "Please analyze this code"
        )
        self.assertIsNotNone(task)
        self.assertEqual(task.status, STATUS_PENDING)

    @patch("urllib.request.urlopen")
    def test_delegate_task_network_error(self, mock_urlopen):
        """delegate_task() returns failed task on network error."""
        mock_urlopen.side_effect = urllib.error.URLError("refused")
        task = self.client.delegate_task("http://bad.example.com", "work")
        self.assertEqual(task.status, STATUS_FAILED)
        self.assertIsNotNone(task.error)

    def test_get_discovered_agents_empty(self):
        """get_discovered_agents() returns empty list initially."""
        agents = self.client.get_discovered_agents()
        self.assertEqual(agents, [])


# ---------------------------------------------------------------------------
# Test Suite: AgentCardGenerator
# ---------------------------------------------------------------------------

class TestAgentCardGenerator(unittest.TestCase):
    """Tests for BCH agent card auto-generation."""

    def test_generate_all_returns_five_agents(self):
        """generate_all() returns cards for all 5 BCH agents."""
        cards = AgentCardGenerator.generate_all()
        self.assertEqual(len(cards), 5)
        names = {c.name for c in cards}
        self.assertEqual(names, {"ATLAS", "FORGE", "CLIO", "NEXUS", "BOLT"})

    def test_all_cards_have_skills(self):
        """All generated cards have at least one skill."""
        for card in AgentCardGenerator.generate_all():
            self.assertTrue(
                len(card.skills) > 0,
                f"{card.name} has no skills"
            )

    def test_generate_for_atlas(self):
        """generate_for_agent() returns ATLAS card."""
        card = AgentCardGenerator.generate_for_agent("ATLAS")
        self.assertIsNotNone(card)
        self.assertEqual(card.name, "ATLAS")

    def test_generate_for_unknown_agent(self):
        """generate_for_agent() returns None for unknown agent."""
        card = AgentCardGenerator.generate_for_agent("UNKNOWN_AGENT_XYZ")
        self.assertIsNone(card)

    def test_case_insensitive_agent_name(self):
        """generate_for_agent() is case-insensitive."""
        card_lower = AgentCardGenerator.generate_for_agent("atlas")
        card_upper = AgentCardGenerator.generate_for_agent("ATLAS")
        self.assertIsNotNone(card_lower)
        self.assertEqual(card_lower.name, card_upper.name)

    def test_custom_host_and_port(self):
        """generate_for_agent() uses custom host and port."""
        card = AgentCardGenerator.generate_for_agent("FORGE", host="myhost", port=9999)
        self.assertIn("myhost", card.url)
        self.assertIn("9999", card.url)


# ---------------------------------------------------------------------------
# Test Suite: ProtocolBridge
# ---------------------------------------------------------------------------

class TestProtocolBridge(unittest.TestCase):
    """Tests for ProtocolBridge orchestrator."""

    def setUp(self):
        """Create bridge with temp database."""
        self.db = temp_db()
        self.bridge = ProtocolBridge(
            db_path=self.db,
            mcp_port=18765,
            a2a_port=18766,
            log_path=None
        )

    def test_register_bch_agent_returns_card(self):
        """register_bch_agent() returns AgentCard."""
        card = self.bridge.register_bch_agent(
            "ATLAS", "Implementation Lead"
        )
        self.assertIsNotNone(card)
        self.assertEqual(card.name, "ATLAS")

    def test_register_bch_agent_stores_in_registry(self):
        """Registered agent appears in registry."""
        self.bridge.register_bch_agent("FORGE", "Orchestrator")
        card = self.bridge.registry.get_agent("FORGE")
        self.assertIsNotNone(card)

    def test_get_mcp_handler_after_register(self):
        """get_mcp_handler() returns protocol after registration."""
        self.bridge.register_bch_agent("CLIO", "CLI Agent")
        handler = self.bridge.get_mcp_handler("CLIO")
        self.assertIsNotNone(handler)

    def test_get_mcp_handler_unregistered(self):
        """get_mcp_handler() returns None for unregistered agent."""
        handler = self.bridge.get_mcp_handler("NOBODY")
        self.assertIsNone(handler)

    def test_status_returns_expected_keys(self):
        """status() returns dict with expected keys."""
        status = self.bridge.status()
        expected_keys = [
            "bridge_version", "mcp_port", "a2a_port",
            "registered_agents", "agent_names", "recent_tasks",
            "servers_running", "database"
        ]
        for key in expected_keys:
            self.assertIn(key, status, f"Missing key: {key}")

    def test_status_version_matches(self):
        """status() reports correct bridge version."""
        status = self.bridge.status()
        self.assertEqual(status["bridge_version"], VERSION)

    def test_register_agent_with_tools(self):
        """register_bch_agent() stores tools in registry."""
        tools = [MCPTool(name="ping", description="Ping")]
        self.bridge.register_bch_agent("NEXUS", "Architect", tools=tools)
        stored_tools = self.bridge.registry.get_tools_for_agent("NEXUS")
        self.assertEqual(len(stored_tools), 1)
        self.assertEqual(stored_tools[0].name, "ping")


# ---------------------------------------------------------------------------
# Test Suite: MCPStdioAdapter
# ---------------------------------------------------------------------------

class TestMCPStdioAdapter(unittest.TestCase):
    """Tests for MCP stdio transport adapter."""

    def setUp(self):
        """Create protocol and stdio adapter."""
        tool = MCPTool(name="echo", description="Echo input")
        self.proto = MCPProtocol(
            server_name="TestServer",
            tools=[tool]
        )
        self.proto.register_tool_handler(
            "echo", lambda args: args.get("text", "")
        )
        self.adapter = MCPStdioAdapter(self.proto)

    def test_process_message_initialize(self):
        """Adapter processes initialize request."""
        req = make_jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp = self.adapter.process_message(req)
        self.assertIsNotNone(resp)
        d = json.loads(resp)
        self.assertIn("result", d)

    def test_process_message_tool_call(self):
        """Adapter processes tools/call request."""
        req = make_jsonrpc("tools/call", {"name": "echo", "arguments": {"text": "hello"}})
        resp = self.adapter.process_message(req)
        self.assertIsNotNone(resp)
        d = json.loads(resp)
        self.assertIn("result", d)
        self.assertIn("hello", d["result"]["content"][0]["text"])

    def test_process_notification_returns_none(self):
        """Adapter returns None for notifications."""
        notif = make_notification("notifications/initialized")
        result = self.adapter.process_message(notif)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Test Suite: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    """Edge cases and error condition tests."""

    def test_empty_tools_list_in_protocol(self):
        """MCPProtocol with no tools returns empty tools list."""
        proto = MCPProtocol("EmptyServer")
        req = make_jsonrpc("tools/list", {})
        resp = json.loads(proto.handle_request(req))
        self.assertEqual(resp["result"]["tools"], [])

    def test_registry_creates_parent_dirs(self):
        """CapabilityRegistry creates parent directories as needed."""
        nested_path = Path(tempfile.mkdtemp()) / "a" / "b" / "c" / "test.db"
        registry = CapabilityRegistry(nested_path)
        self.assertTrue(nested_path.exists())

    def test_version_constant_is_string(self):
        """VERSION constant is a non-empty string."""
        self.assertIsInstance(VERSION, str)
        self.assertGreater(len(VERSION), 0)

    def test_agent_card_authentication_default(self):
        """AgentCard has default authentication scheme."""
        card = AgentCard(name="A", description="B", url="http://c")
        self.assertIn("schemes", card.authentication)

    def test_mcp_error_stores_code_and_message(self):
        """MCPError stores code and message attributes."""
        err = MCPError(-32602, "Invalid params")
        self.assertEqual(err.code, -32602)
        self.assertEqual(err.message, "Invalid params")

    def test_protocol_bridge_status_no_agents(self):
        """Bridge status shows 0 agents on fresh database."""
        bridge = ProtocolBridge(db_path=temp_db(), log_path=None)
        status = bridge.status()
        self.assertEqual(status["registered_agents"], 0)
        self.assertEqual(status["agent_names"], [])

    def test_a2a_task_to_dict_none_result(self):
        """A2ATask.to_dict() handles None result gracefully."""
        task = A2ATask(task_id="x", agent_name="A", message="m")
        d = task.to_dict()
        self.assertIsNone(d["result"])

    def test_registry_task_update(self):
        """Logging same task_id updates the record."""
        db = temp_db()
        registry = CapabilityRegistry(db)
        task = A2ATask(
            task_id="up-001",
            agent_name="ATLAS",
            message="work",
            status=STATUS_PENDING
        )
        registry.log_task(task)

        task.status = STATUS_COMPLETED
        task.result = "Done!"
        registry.log_task(task)

        updated = registry.get_task("up-001")
        self.assertEqual(updated.status, STATUS_COMPLETED)
        self.assertEqual(updated.result, "Done!")


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------

def run_tests() -> int:
    """Run all tests with formatted output."""
    print("=" * 70)
    print("  MCPBridge v1.0 - Test Suite")
    print("  Agent: ATLAS (Team Brain)")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestAgentCard,
        TestMCPDataClasses,
        TestCapabilityRegistry,
        TestMCPProtocol,
        TestA2ATask,
        TestA2AClientModule,
        TestAgentCardGenerator,
        TestProtocolBridge,
        TestMCPStdioAdapter,
        TestEdgeCases,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 70)
    print(f"  RESULTS: {result.testsRun} tests run")
    print(f"  [OK] Passed: {passed}")
    if result.failures:
        print(f"  [X]  Failed: {len(result.failures)}")
    if result.errors:
        print(f"  [X]  Errors: {len(result.errors)}")
    print(f"  {'[OK] ALL TESTS PASSED' if result.wasSuccessful() else '[X] FAILURES DETECTED'}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
