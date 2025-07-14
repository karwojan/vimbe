import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass
class EventMessage:
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "EventMessage":
        t = d.get("type")
        # dispatch based on event type
        if t == "error":
            return ErrorEvent(message=d.get("message"))
        if t == "task_started":
            return TaskStarted()
        if t == "task_complete":
            return TaskCompleteEvent(last_agent_message=d.get("last_agent_message"))
        if t == "token_count":
            return TokenCount(
                input_tokens=d.get("input_tokens", 0),
                cached_input_tokens=d.get("cached_input_tokens"),
                output_tokens=d.get("output_tokens", 0),
                reasoning_output_tokens=d.get("reasoning_output_tokens"),
                total_tokens=d.get("total_tokens", 0),
            )
        if t == "agent_message":
            return AgentMessageEvent(message=d.get("message"))
        if t == "agent_reasoning":
            return AgentReasoningEvent(text=d.get("text"))
        if t == "session_configured":
            return SessionConfiguredEvent(
                session_id=d.get("session_id"),
                model=d.get("model"),
                history_log_id=d.get("history_log_id", 0),
                history_entry_count=d.get("history_entry_count", 0),
            )
        if t == "mcp_tool_call_begin":
            return McpToolCallBeginEvent(
                call_id=d.get("call_id"),
                server=d.get("server"),
                tool=d.get("tool"),
                arguments=d.get("arguments"),
            )
        if t == "mcp_tool_call_end":
            return McpToolCallEndEvent(
                call_id=d.get("call_id"),
                result=d.get("result"),
            )
        if t == "exec_command_begin":
            return ExecCommandBeginEvent(
                call_id=d.get("call_id"),
                command=d.get("command", []),
                cwd=d.get("cwd"),
            )
        if t == "exec_command_end":
            return ExecCommandEndEvent(
                call_id=d.get("call_id"),
                stdout=d.get("stdout"),
                stderr=d.get("stderr"),
                exit_code=d.get("exit_code", 0),
            )
        if t == "exec_approval_request":
            return ExecApprovalRequestEvent(
                command=d.get("command", []),
                cwd=d.get("cwd"),
                reason=d.get("reason"),
            )
        if t == "apply_patch_approval_request":
            # parse file changes
            changes = {
                p: FileChange.from_dict(ch) for p, ch in d.get("changes", {}).items()
            }
            return ApplyPatchApprovalRequestEvent(
                changes=changes,
                reason=d.get("reason"),
                grant_root=d.get("grant_root"),
            )
        if t == "background_event":
            return BackgroundEvent(message=d.get("message"))
        if t == "patch_apply_begin":
            changes = {
                p: FileChange.from_dict(ch) for p, ch in d.get("changes", {}).items()
            }
            return PatchApplyBeginEvent(
                call_id=d.get("call_id"),
                auto_approved=d.get("auto_approved", False),
                changes=changes,
            )
        if t == "patch_apply_end":
            return PatchApplyEndEvent(
                call_id=d.get("call_id"),
                stdout=d.get("stdout"),
                stderr=d.get("stderr"),
                success=d.get("success", False),
            )
        if t == "get_history_entry_response":
            entry = d.get("entry")
            hist = HistoryEntry(**entry) if entry is not None else None
            return GetHistoryEntryResponseEvent(
                offset=d.get("offset", 0),
                log_id=d.get("log_id", 0),
                entry=hist,
            )
        # unknown type
        return UnknownEvent(d)


@dataclass
class Event:
    id: str
    message: EventMessage

    @staticmethod
    def from_json(json_text: str) -> "Event":
        d = json.loads(json_text)
        return Event(id=d["id"], message=EventMessage.from_dict(d["msg"]))


@dataclass
class UnknownEvent(EventMessage):
    def __init__(self, data: dict[str, Any]):
        self.data = data


class FileChangeType(Enum):
    ADD = "add"
    DELETE = "delete"
    UPDATE = "update"


@dataclass
class FileChange:
    type: FileChangeType
    content: str | None = None
    unified_diff: str | None = None
    move_path: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FileChange":
        t = d.get("type")
        if t == "add":
            return FileChange(type=FileChangeType.ADD, content=d.get("content"))
        if t == "delete":
            return FileChange(type=FileChangeType.DELETE)
        if t == "update":
            return FileChange(
                type=FileChangeType.UPDATE,
                unified_diff=d.get("unified_diff"),
                move_path=d.get("move_path"),
            )
        # unknown, default to delete
        return FileChange(type=FileChangeType.DELETE)


@dataclass
class HistoryEntry:
    session_id: str
    ts: int
    text: str


@dataclass
class ErrorEvent(EventMessage):
    message: str


@dataclass
class TaskStarted(EventMessage):
    pass


@dataclass
class TaskCompleteEvent(EventMessage):
    last_agent_message: str | None


@dataclass
class TokenCount(EventMessage):
    input_tokens: int
    cached_input_tokens: int | None
    output_tokens: int
    reasoning_output_tokens: int | None
    total_tokens: int


@dataclass
class AgentMessageEvent(EventMessage):
    message: str


@dataclass
class AgentReasoningEvent(EventMessage):
    text: str


@dataclass
class SessionConfiguredEvent(EventMessage):
    session_id: str
    model: str
    history_log_id: int
    history_entry_count: int


@dataclass
class McpToolCallBeginEvent(EventMessage):
    call_id: str
    server: str
    tool: str
    arguments: Any


@dataclass
class McpToolCallEndEvent(EventMessage):
    call_id: str
    result: Any


@dataclass
class ExecCommandBeginEvent(EventMessage):
    call_id: str
    command: list[str]
    cwd: str


@dataclass
class ExecCommandEndEvent(EventMessage):
    call_id: str
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class ExecApprovalRequestEvent(EventMessage):
    command: list[str]
    cwd: str
    reason: str | None


@dataclass
class ApplyPatchApprovalRequestEvent(EventMessage):
    changes: dict[str, FileChange]
    reason: str | None
    grant_root: str | None


@dataclass
class BackgroundEvent(EventMessage):
    message: str


@dataclass
class PatchApplyBeginEvent(EventMessage):
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]


@dataclass
class PatchApplyEndEvent(EventMessage):
    call_id: str
    stdout: str
    stderr: str
    success: bool


@dataclass
class GetHistoryEntryResponseEvent(EventMessage):
    offset: int
    log_id: int
    entry: HistoryEntry | None
