import vim

from codex_protocol_submission import (
    Submission,
    SubmissionOperation,
    Interrupt,
    TextInput,
    UserInput,
    ExecApproval,
    PatchApproval,
    ReviewDecision,
)
from codex_protocol_event import (
    Event,
    AgentMessageEvent,
    AgentReasoningEvent,
    ErrorEvent,
    TaskStarted,
    TaskCompleteEvent,
    ExecCommandEndEvent,
    ExecApprovalRequestEvent,
    ApplyPatchApprovalRequestEvent,
    PatchApplyEndEvent,
)

# functions handlers
bufadd = vim.Function("bufadd")
bufload = vim.Function("bufload")


class CodexBuffers:
    def __init__(
        self,
        input_buffer_setup_commands: list[str] = None,
        output_buffer_setup_commands: list[str] = None,
    ):
        self.input_buffer_setup_commands = input_buffer_setup_commands
        self.output_buffer_setup_commands = output_buffer_setup_commands

        # vim.buffers is a mapping nr->buffer
        self.output_buffer = vim.buffers[bufadd("")]
        bufload(self.output_buffer.number)
        self.output_buffer.name = "CODEX output"
        self.output_buffer.options["buftype"] = "nofile"
        self.output_buffer.options["modifiable"] = False
        self.output_buffer.options["swapfile"] = False

        self.input_buffer = vim.buffers[bufadd("")]
        bufload(self.input_buffer.number)
        self.input_buffer.name = "CODEX prompt"
        self.input_buffer.options["buftype"] = "nofile"
        self.input_buffer.options["swapfile"] = False

    def _find_window(self, buffer: vim.Buffer) -> vim.Window | None:
        # vim.windows is a sequence, which we have to search over
        target_windows = [w for w in vim.windows if w.buffer == buffer]
        return target_windows[0] if len(target_windows) > 0 else None

    def append_output(self, text: str) -> None:
        self.output_buffer.options["modifiable"] = True
        self.output_buffer.append(text.splitlines())
        self.output_buffer.options["modifiable"] = False
        output_window = self._find_window(self.output_buffer)
        if output_window is not None and output_window.height > 0:
            old_current_window = vim.current.window
            vim.current.window = output_window
            vim.command("normal G")
            vim.current.window = old_current_window

    def hide(self):
        output_window = self._find_window(self.output_buffer)
        if output_window is not None:
            vim.command(f"{output_window.number}hide")
        input_window = self._find_window(self.input_buffer)
        if input_window is not None:
            vim.command(f"{input_window.number}hide")

    def show(self):
        vim.command(f"botright vertical sbuffer {self.output_buffer.number}")
        output_window = self._find_window(self.output_buffer)
        output_window.width = 60
        vim.current.window = output_window
        if self.output_buffer_setup_commands is not None:
            for cmd in self.output_buffer_setup_commands:
                vim.command(cmd)
        vim.command(f"below horizontal sbuffer {self.input_buffer.number}")
        input_window = self._find_window(self.input_buffer)
        input_window.height = 5
        vim.current.window = input_window
        if self.input_buffer_setup_commands is not None:
            for cmd in self.input_buffer_setup_commands:
                vim.command(cmd)

    def switch(self):
        if (
            self._find_window(self.input_buffer) is None
            or self._find_window(self.output_buffer) is None
        ):
            self.hide()  # make sure there is only one instance of windows
            self.show()
        else:
            self.hide()


class CodexSession:
    sessions: list["CodexSession"] = []

    def __init__(self):
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
                f"nmap <buffer> <Enter> :py3 codex.CodexSession.sessions[{self.session_idx}].send_user_message()<CR>"
            ]
        )
        self.codex_buffers.show()

    def _handle_agent_message(self, message: AgentMessageEvent) -> None:
        self.codex_buffers.append_output(
            f"-----ASSISTANT-----\n{message.message}\n-------------------"
        )

    def _handle_agent_reasoning(self, message: AgentReasoningEvent) -> None:
        self.codex_buffers.append_output(
            f"-----REASONING-----\n{message.text}\n-------------------"
        )

    def _handle_error(self, message: ErrorEvent) -> None:
        pass  # TODO

    def _handle_task_started(self, message: TaskStarted) -> None:
        pass  # TODO

    def _handle_task_completed(self, message: TaskCompleteEvent) -> None:
        pass  # TODO

    def _handle_exec_approval_request(self, message: ExecApprovalRequestEvent) -> None:
        pass  # TODO

    def _handle_exec_command_end(self, message: ExecCommandEndEvent) -> None:
        pass  # TODO

    def _handle_apply_patch_approval_request(
        self, message: ApplyPatchApprovalRequestEvent
    ) -> None:
        pass  # TODO

    def _handle_patch_apply_end(self, message: PatchApplyEndEvent) -> None:
        pass  # TODO

    def _handle_job_output(self, message: str) -> None:
        event = Event.from_json(message)
        #######
        self.codex_buffers.append_output(str(event))
        #######
        if isinstance(event.message, AgentMessageEvent):
            self._handle_agent_message(event.message)
        elif isinstance(event.message, AgentReasoningEvent):
            self._handle_agent_reasoning(event.message)
        elif isinstance(event.message, ErrorEvent):
            self._handle_error(event.message)
        elif isinstance(event.message, TaskStarted):
            self._handle_task_started(event.message)
        elif isinstance(event.message, TaskCompleteEvent):
            self._handle_task_completed(event.message)
        elif isinstance(event.message, ExecApprovalRequestEvent):
            self._handle_exec_approval_request(event.message)
        elif isinstance(event.message, ExecCommandEndEvent):
            self._handle_exec_command_end(event.message)
        elif isinstance(event.message, ApplyPatchApprovalRequestEvent):
            self._handle_apply_patch_approval_request(event.message)
        elif isinstance(event.message, PatchApplyEndEvent):
            self._handle_patch_apply_end(event.message)

    def _send(self, op: SubmissionOperation) -> str:
        submission = Submission(operation=op)
        self._send_to_job(submission.to_json() + "\n")
        return str(submission.id)

    def interrupt(self) -> str:
        return self._send(Interrupt())

    def send_user_message(self):
        text = "\n".join(self.codex_buffers.input_buffer[:])
        del self.codex_buffers.input_buffer[:]
        self.codex_buffers.append_output(f"-----USER-----\n{text}\n--------------")
        return self._send(UserInput([TextInput(text)]))

    def exec_approval(self, id: str, decision: ReviewDecision) -> str:
        return self._send(ExecApproval(id, ReviewDecision))

    def patch_approval(self, id: str, decision: ReviewDecision) -> str:
        return self._send(PatchApproval(id, ReviewDecision))

    def stop(self) -> None:
        self._stop_job()
        self.codex_buffers.hide()


codex_session: CodexSession | None = None


def if_session_exists(func):
    def wrapper():
        if codex_session is not None:
            func()
        else:
            print("Codex session does not exist.")

    return wrapper


def start_codex_session():
    global codex_session
    if codex_session is None:
        codex_session = CodexSession()
    else:
        print("Codex session already exists.")


@if_session_exists
def stop_codex_session():
    global codex_session
    codex_session.stop()
    codex_session = None


@if_session_exists
def switch_codex_window():
    codex_session.codex_buffers.switch()
