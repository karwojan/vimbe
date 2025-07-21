# VImBE

This is [CodexCLI](https://github.com/openai/codex) integration plugin for Vim.

> It is very early development stage, and it is going to change dynamically.

## Installation

You can install this plugin with vim-plug:
```
Plug 'karwojan/vimbe'
```

Under the hood, this plugin launches `codex` in the background (the command
must be available in your PATH) and communicates with it via
[protocol](https://github.com/openai/codex/blob/main/codex-rs/docs/protocol_v1.md).

## Usage

Basic workflow:

1. **Start a session**: Press \<Leader>cs to begin
2. **Type your prompt**: In the bottom input window, type what you want Codex to do
3. **Send message**: Press `Enter` to send your message
4. **Review output**: Watch the top window for Codex responses
5. **Approve actions**: When Codex needs to execute commands or apply patches, use `Ctrl+A` (approve) or `Ctrl+D` (deny)
6. **Interrupt if needed**: Press `Ctrl+C` to stop ongoing operations
7. **Close session**: Press \<Leader>cS to stop the session

#### General mapping:
- `<Leader>cs` - Start a new Codex session
- `<Leader>cS` - Stop the current Codex session
- `<Leader>cc` - Toggle Codex window visibility (show/hide)

#### Input Window mapping (bottom panel):
The input window is where you type your prompts and interact with Codex.

- `Enter` (normal mode) - Send your message to Codex
- `Ctrl+C` - Interrupt the current Codex operation
- `Ctrl+A` - Approve the pending request (exec/patch)
- `Ctrl+D` - Deny the pending request (exec/patch)
