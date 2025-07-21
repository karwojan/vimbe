import re
import subprocess
from contextlib import contextmanager
from typing import Callable, Literal

import vim
from codex_protocol_event import (
    AgentMessageEvent,
    AgentReasoningEvent,
    ApplyPatchApprovalRequestEvent,
    ErrorEvent,
    Event,
    ExecApprovalRequestEvent,
    ExecCommandBeginEvent,
    ExecCommandEndEvent,
    FileChange,
    FileChangeType,
    PatchApplyBeginEvent,
    PatchApplyEndEvent,
    TaskCompleteEvent,
    TaskStarted,
)
from codex_protocol_submission import (
    ExecApproval,
    Interrupt,
    PatchApproval,
    ReviewDecision,
    Submission,
    SubmissionOperation,
    TextInput,
    UserInput,
)

# functions handlers
bufadd = vim.Function("bufadd")
bufload = vim.Function("bufload")
timer_start = vim.Function("timer_start")


@contextmanager
def vim_window(window: vim.Window) -> None:
    old_current_window = vim.current.window
    vim.current.window = window
    try:
        yield None
    finally:
        vim.current.window = old_current_window


def find_window(buffer: vim.Buffer) -> vim.Window | None:
    # vim.windows is a sequence, which we have to search over
    target_windows = [w for w in vim.windows if w.buffer == buffer]
    return target_windows[0] if len(target_windows) > 0 else None


class CodexBuffers:
    def __init__(
        self,
        input_buffer_setup_commands: list[str] | None = None,
        output_buffer_setup_commands: list[str] | None = None,
    ) -> None:
        self.input_buffer_setup_commands = input_buffer_setup_commands
        self.output_buffer_setup_commands = output_buffer_setup_commands

        # vim.buffers is a mapping nr->buffer
        self.output_buffer = vim.buffers[bufadd("")]
        bufload(self.output_buffer.number)
        self.output_buffer.name = "CODEX output [READY]"
        self.output_buffer.options["buftype"] = "nofile"
        self.output_buffer.options["modifiable"] = False
        self.output_buffer.options["swapfile"] = False
        self.output_buffer.options["filetype"] = "codexoutput"

        self.input_buffer = vim.buffers[bufadd("")]
        bufload(self.input_buffer.number)
        self.input_buffer.name = "CODEX prompt"
        self.input_buffer.options["buftype"] = "nofile"
        self.input_buffer.options["swapfile"] = False

    @property
    def output_window(self) -> vim.Window | None:
        return find_window(self.output_buffer)

    @property
    def input_window(self) -> vim.Window | None:
        return find_window(self.input_buffer)

    def append_output(self, text: str) -> None:
        self.output_buffer.options["modifiable"] = True
        self.output_buffer.append(text.splitlines() + [""])
        self.output_buffer.options["modifiable"] = False
        if self.output_window is not None and self.output_window.height > 0:
            with vim_window(self.output_window):
                vim.command("normal G")

    def replace_last_output_line(self, pattern: str, repl: str) -> None:
        self.output_buffer.options["modifiable"] = True
        for idx in reversed(range(len(self.output_buffer))):
            line = self.output_buffer[idx]
            if re.search(pattern, line) is not None:
                self.output_buffer[idx] = re.sub(pattern, repl, line)
        self.output_buffer.options["modifiable"] = False

    def show_status_in_input(self, message: str) -> None:
        self.input_buffer.options["modifiable"] = True
        self.input_buffer[:] = message.splitlines()
        self.input_buffer.options["modifiable"] = False

    def hide_status_in_input(self) -> None:
        self.input_buffer.options["modifiable"] = True
        self.input_buffer[:] = []

    def hide(self) -> None:
        if self.output_window is not None:
            vim.command(f"{self.output_window.number}hide")
        if self.input_window is not None:
            vim.command(f"{self.input_window.number}hide")

    def show(self) -> None:
        vim.command(f"botright vertical sbuffer {self.output_buffer.number}")

        self.output_window.width = 70
        with vim_window(self.output_window):
            vim.command("syntax on")
            if self.output_buffer_setup_commands is not None:
                for cmd in self.output_buffer_setup_commands:
                    vim.command(cmd)
            vim.command(f"below horizontal sbuffer {self.input_buffer.number}")

        self.input_window.height = 5
        with vim_window(self.input_window):
            if self.input_buffer_setup_commands is not None:
                for cmd in self.input_buffer_setup_commands:
                    vim.command(cmd)

        vim.current.window = self.input_window

    def switch(self) -> None:
        if self.input_window is None or self.output_window is None:
            self.hide()  # make sure there is only one instance of windows
            self.show()
        else:
            self.hide()

    def delete(self) -> None:
        vim.command(f"bdelete {self.output_buffer.number}")
        vim.command(f"bdelete {self.input_buffer.number}")


class ApplyPatchBuffer:
    def __init__(self) -> None:
        self.patch_buffer = vim.buffers[bufadd("")]
        bufload(self.patch_buffer.number)
        self.patch_buffer.name = "patched"
        self.patch_buffer.options["buftype"] = "nofile"
        self.patch_buffer.options["swapfile"] = False

        self.largest_window: vim.Window | None = None

    @property
    def patch_window(self) -> vim.Window | None:
        return find_window(self.patch_buffer)

    def _apply_patch_in_memory(self, path: str, unified_diff: str) -> str:
        p = subprocess.Popen(
            ["patch", "-i", "-", "-o", "-", path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(unified_diff)
        return stdout

    def show(self, path: str, unified_diff: str) -> None:
        patched_content = self._apply_patch_in_memory(path, unified_diff)
        self.patch_buffer[:] = patched_content.splitlines()
        self.largest_window = max(vim.windows, key=lambda w: w.width)
        with vim_window(self.largest_window):
            vim.command(f"edit {path}")
            vim.command("diffthis")
            vim.command(f"vertical sbuffer {self.patch_buffer.number}")
        with vim_window(self.patch_window):
            vim.command("diffthis")

    def hide(self) -> None:
        if self.patch_window is not None:
            with vim_window(self.largest_window):
                vim.command("diffoff")
            vim.command(f"{self.patch_window.number}hide")

    def delete(self) -> None:
        vim.command(f"bdelete {self.patch_buffer.number}")


class CodexSession:
    sessions: list["CodexSession"] = []

    def __init__(self) -> None:
        self.session_idx = len(self.sessions)
        self.sessions.append(self)

        # this is necessary as there is no type for Job in python (all the methods
        # return None instead of Job), so the Job reference can not be hold in python
        vim.command(
            f"""\
            function HandleCodexJobOutput{self.session_idx}(channel, msg)
                py3 codex.CodexSession.sessions[{self.session_idx}]._handle_job_output(vim.eval("a:msg"))
            endfunction
            let g:codex_job{self.session_idx} = job_start(["codex", "proto"], \
                    {{"out_mode": "nl", "out_cb": "HandleCodexJobOutput{self.session_idx}"}})
            function SendToCodexJob{self.session_idx}(msg)
                call ch_sendraw(g:codex_job{self.session_idx}, a:msg)
            endfunction
            function StopCodexJob{self.session_idx}()
                call job_stop(g:codex_job{self.session_idx}, "kill")
            endfunction
        """
        )
        self._send_to_job = vim.Function(f"SendToCodexJob{self.session_idx}")
        self._stop_job = vim.Function(f"StopCodexJob{self.session_idx}")

        self.codex_buffers = CodexBuffers(
            input_buffer_setup_commands=[
                f"nmap <buffer> <Enter> :py3 codex.CodexSession.sessions[{self.session_idx}].send_user_message()<CR>",
                f"nmap <buffer> <C-C> :py3 codex.CodexSession.sessions[{self.session_idx}].interrupt()<CR>",
                f"nmap <buffer> <C-A> :py3 codex.CodexSession.sessions[{self.session_idx}].approval(codex.ReviewDecision.APPROVED)<CR>",
                f"nmap <buffer> <C-D> :py3 codex.CodexSession.sessions[{self.session_idx}].approval(codex.ReviewDecision.DENIED)<CR>",
            ]
        )
        self.codex_buffers.show()

        self.apply_patch_buffer = ApplyPatchBuffer()

        self.last_approval_request_type: Literal["exec", "patch"] | None = None
        self.last_approval_request_submission_id: str | None = None

    def _handle_agent_message(self, id: str, message: AgentMessageEvent) -> None:
        self.codex_buffers.append_output(f"codex\n{message.message}")

    def _handle_agent_reasoning(self, id: str, message: AgentReasoningEvent) -> None:
        self.codex_buffers.append_output(f"codex (reasoning)\n{message.text}")

    def _handle_error(self, id: str, message: ErrorEvent) -> None:
        self.codex_buffers.append_output(f"ERROR\n{message.message}")

    def _handle_task_started(self, id: str, message: TaskStarted) -> None:
        self.codex_buffers.output_buffer.name = "CODEX output [THINKING...]"

    def _handle_task_completed(self, id: str, message: TaskCompleteEvent) -> None:
        self.codex_buffers.output_buffer.name = "CODEX output [READY]"

    def _handle_exec_approval_request(
        self, id: str, message: ExecApprovalRequestEvent
    ) -> None:
        self.last_approval_request_type = "exec"
        self.last_approval_request_submission_id = id
        self.codex_buffers.show_status_in_input(
            f"EXEC APPROVAL REQUEST: {message.reason or ''}\n"
            f"[{message.cwd}]$ {' '.join(message.command)}"
        )

    def _handle_exec_command_begin(
        self, id: str, message: ExecCommandBeginEvent
    ) -> None:
        self.codex_buffers.append_output(
            f"command (running...)\n$ {' '.join(message.command)}"
        )

    def _handle_exec_command_end(self, id: str, message: ExecCommandEndEvent) -> None:
        self.codex_buffers.replace_last_output_line(
            r"command \(running\.\.\.\)",
            f"command ({'OK' if message.exit_code == 0 else 'ERROR'})",
        )

    def _file_changes_summary(self, changes: dict[str, FileChange]) -> str:
        return "\n".join(
            f"{change.type.value} {path}" for path, change in changes.items()
        )

    def _handle_apply_patch_approval_request(
        self, id: str, message: ApplyPatchApprovalRequestEvent
    ) -> None:
        self.last_approval_request_type = "patch"
        self.last_approval_request_submission_id = id
        self.codex_buffers.show_status_in_input(
            f"PATCH APPROVAL REQUEST: {message.reason or ''}\n"
            + self._file_changes_summary(message.changes)
        )
        update_changes = [
            (p, ch)
            for p, ch in message.changes.items()
            if ch.type == FileChangeType.UPDATE
        ]
        if len(update_changes) > 0:
            path, change = next(iter(update_changes))
            self.apply_patch_buffer.show(path, change.unified_diff)

    def _handle_patch_apply_begin(self, id: str, message: PatchApplyBeginEvent) -> None:
        self.codex_buffers.append_output(str(message))  # TODO

    def _handle_patch_apply_end(self, id: str, message: PatchApplyEndEvent) -> None:
        self.codex_buffers.append_output(str(message))  # TODO

    def _handle_job_output(self, message_str: str) -> None:
        event = Event.from_json(message_str)
        if isinstance(event.message, AgentMessageEvent):
            self._handle_agent_message(event.id, event.message)
        elif isinstance(event.message, AgentReasoningEvent):
            self._handle_agent_reasoning(event.id, event.message)
        elif isinstance(event.message, ErrorEvent):
            self._handle_error(event.id, event.message)
        elif isinstance(event.message, TaskStarted):
            self._handle_task_started(event.id, event.message)
        elif isinstance(event.message, TaskCompleteEvent):
            self._handle_task_completed(event.id, event.message)
        elif isinstance(event.message, ExecApprovalRequestEvent):
            self._handle_exec_approval_request(event.id, event.message)
        elif isinstance(event.message, ExecCommandBeginEvent):
            self._handle_exec_command_begin(event.id, event.message)
        elif isinstance(event.message, ExecCommandEndEvent):
            self._handle_exec_command_end(event.id, event.message)
        elif isinstance(event.message, ApplyPatchApprovalRequestEvent):
            self._handle_apply_patch_approval_request(event.id, event.message)
        elif isinstance(event.message, PatchApplyBeginEvent):
            self._handle_patch_apply_begin(event.id, event.message)
        elif isinstance(event.message, PatchApplyEndEvent):
            self._handle_patch_apply_end(event.id, event.message)
        else:
            self.codex_buffers.append_output(str(event.message))

    def _send(self, op: SubmissionOperation) -> None:
        submission = Submission(operation=op)
        self._send_to_job(submission.to_json() + "\n")

    def interrupt(self) -> None:
        self._send(Interrupt())

    def send_user_message(self) -> None:
        text = "\n".join(self.codex_buffers.input_buffer[:])
        del self.codex_buffers.input_buffer[:]
        self.codex_buffers.append_output(f"\nuser\n{text}\n")
        self._send(UserInput([TextInput(text)]))

    def approval(self, decision: ReviewDecision) -> None:
        if self.last_approval_request_type is not None:
            if self.last_approval_request_type == "exec":
                self._send(
                    ExecApproval(self.last_approval_request_submission_id, decision)
                )
            elif self.last_approval_request_type == "patch":
                self._send(
                    PatchApproval(self.last_approval_request_submission_id, decision)
                )
                self.apply_patch_buffer.hide()
            self.codex_buffers.hide_status_in_input()
            self.last_approval_request_type = None

    def stop(self) -> None:
        self._stop_job()
        self.codex_buffers.delete()
        self.apply_patch_buffer.delete()


codex_session: CodexSession | None = None


def if_session_exists(func) -> Callable:
    def wrapper() -> None:
        if codex_session is not None:
            func()
        else:
            print("Codex session does not exist.")

    return wrapper


def start_codex_session() -> None:
    global codex_session
    if codex_session is None:
        codex_session = CodexSession()
    else:
        print("Codex session already exists.")


@if_session_exists
def stop_codex_session() -> None:
    global codex_session
    codex_session.stop()
    codex_session = None


@if_session_exists
def switch_codex_window() -> None:
    codex_session.codex_buffers.switch()
