import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


@dataclass
class SubmissionOperation:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError()


@dataclass
class Submission:
    operation: SubmissionOperation
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_json(self) -> str:
        return json.dumps({"id": self.id, "op": self.operation.to_dict()})


# Helper enums and dataclasses for Submission operations


class ReasoningEffort(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    NONE = "none"


class ReasoningSummary(Enum):
    AUTO = "auto"
    CONCISE = "concise"
    DETAILED = "detailed"
    NONE = "none"


class AskForApproval(Enum):
    UNLESS_TRUSTED = "untrusted"
    ON_FAILURE = "on-failure"
    NEVER = "never"


class ReviewDecision(Enum):
    APPROVED = "approved"
    APPROVED_FOR_SESSION = "approved_for_session"
    DENIED = "denied"
    ABORT = "abort"


class WireApi(Enum):
    RESPONSES = "responses"
    CHAT = "chat"


@dataclass
class ModelProviderInfo:
    name: str
    base_url: str
    env_key: str | None = None
    env_key_instructions: str | None = None
    wire_api: WireApi = WireApi.CHAT
    query_params: dict[str, str] | None = None
    http_headers: dict[str, str] | None = None
    env_http_headers: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "env_key": self.env_key,
            "env_key_instructions": self.env_key_instructions,
            "wire_api": self.wire_api.value,
            "query_params": self.query_params,
            "http_headers": self.http_headers,
            "env_http_headers": self.env_http_headers,
        }


@dataclass
class InputItem:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError()


@dataclass
class TextInput(InputItem):
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}


@dataclass
class ImageInput(InputItem):
    image_url: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "image", "image_url": self.image_url}


@dataclass
class LocalImageInput(InputItem):
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "local_image", "path": self.path}


class SandboxPolicy:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError()


@dataclass
class DangerFullAccess(SandboxPolicy):
    def to_dict(self) -> dict[str, Any]:
        return {"mode": "danger-full-access"}


@dataclass
class ReadOnly(SandboxPolicy):
    def to_dict(self) -> dict[str, Any]:
        return {"mode": "read-only"}


@dataclass
class WorkspaceWrite(SandboxPolicy):
    writable_roots: list[str] = field(default_factory=list)
    network_access: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "workspace-write",
            "writable_roots": self.writable_roots,
            "network_access": self.network_access,
        }


# SubmissionOperation subclasses


@dataclass
class ConfigureSession(SubmissionOperation):
    provider: ModelProviderInfo
    model: str
    model_reasoning_effort: ReasoningEffort
    model_reasoning_summary: ReasoningSummary
    cwd: str
    instructions: str | None = None
    approval_policy: AskForApproval = AskForApproval.UNLESS_TRUSTED
    sandbox_policy: SandboxPolicy = field(default_factory=ReadOnly)
    disable_response_storage: bool = False
    notify: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": "configure_session",
            "provider": self.provider.to_dict(),
            "model": self.model,
            "model_reasoning_effort": self.model_reasoning_effort.value,
            "model_reasoning_summary": self.model_reasoning_summary.value,
            "instructions": self.instructions,
            "approval_policy": self.approval_policy.value,
            "sandbox_policy": self.sandbox_policy.to_dict(),
            "disable_response_storage": self.disable_response_storage,
            "cwd": self.cwd,
        }
        if self.notify is not None:
            data["notify"] = self.notify
        return data


@dataclass
class Interrupt(SubmissionOperation):
    def to_dict(self) -> dict[str, Any]:
        return {"type": "interrupt"}


@dataclass
class UserInput(SubmissionOperation):
    items: list[InputItem]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "user_input", "items": [i.to_dict() for i in self.items]}


@dataclass
class ExecApproval(SubmissionOperation):
    id: str
    decision: ReviewDecision

    def to_dict(self) -> dict[str, Any]:
        return {"type": "exec_approval", "id": self.id, "decision": self.decision.value}


@dataclass
class PatchApproval(SubmissionOperation):
    id: str
    decision: ReviewDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "patch_approval",
            "id": self.id,
            "decision": self.decision.value,
        }


@dataclass
class AddToHistory(SubmissionOperation):
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "add_to_history", "text": self.text}


@dataclass
class GetHistoryEntryRequest(SubmissionOperation):
    offset: int
    log_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "get_history_entry_request",
            "offset": self.offset,
            "log_id": self.log_id,
        }
