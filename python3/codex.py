import vim

# functions handlers
bufadd = vim.Function("bufadd")
bufload = vim.Function("bufload")


class CodexBuffers:
    def __init__(self):
        self.output_buffer = vim.buffers[bufadd("")]  # vim.buffers is a mapping nr->buffer
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

    def close(self):
        output_window = self._find_window(self.output_buffer)
        if output_window is not None:
            vim.command(f"{output_window.number}hide")
        input_window = self._find_window(self.input_buffer)
        if input_window is not None:
            vim.command(f"{input_window.number}hide")

    def open(self):
        vim.command(f"botright vertical sbuffer {self.output_buffer.number}")
        output_window = self._find_window(self.output_buffer)
        output_window.width = 60
        vim.current.window = output_window
        vim.command(f"below horizontal sbuffer {self.input_buffer.number}")
        input_window = self._find_window(self.input_buffer)
        input_window.height = 5
        vim.current.window = input_window

    def switch(self):
        if self._find_window(self.input_buffer) is None or self._find_window(self.output_buffer) is None:
            self.close()  # make sure there is only one instance of windows
            self.open()
        else:
            self.close()


codex_buffers = CodexBuffers()


def switch_codex_window():
    codex_buffers.switch()
