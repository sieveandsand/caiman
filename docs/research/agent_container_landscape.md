# Where coding agents run relative to containers

Research note, 2026-09-25. Not a contract or a source of Caiman policy.
This informed the now-resolved D-14. The accepted workflow is
[Session context](../CONTAINER-CONTEXT.md) (S-39); this historical survey does not
define a separate local or container provisioning path.
Products in this area change quickly; **recheck the claims below before relying
on them.**

## Question

For development that uses Docker, does the coding agent usually run on the host
or inside the container? It decides which Caiman setup applies: an agent on the
host can reach the store; an agent in a container cannot.

## Method

Web searches and reading vendor documentation on 2026-09-25. No usage surveys or
download figures were found, so the conclusions rest on vendor recommendations
and on what tools are being built, not on measured popularity.

## Findings

| Pattern | Evidence | Assessment |
|---|---|---|
| **Agent inside a container or microVM** | Anthropic documents a Claude Code Dev Container Feature and reference container, and recommends a container, VM, or sandbox runtime for any `--dangerously-skip-permissions` run [1][2]. Docker ships Docker Sandboxes for Claude Code, Codex, Copilot, Gemini, and others [3][4]. Community tools such as ClaudeBox assume the agent is inside [5] | The dominant pattern whenever there is a container per worktree or per project |
| **Agent on the host, no container** | The default install. Claude Code's built-in Bash sandbox and its sandbox runtime isolate a host agent without Docker, and Anthropic points to them for everyday work [2] | Probably the most common setup overall |
| **Agent on the host, toolchain in a container** | Little written evidence. The one tool found does the reverse: the agent runs in a container and asks the host to build, because the host has the right SDKs, caches, and signing keys [6] | Exists, especially where Docker was adopted only to pin a toolchain; not measurably widespread |
| **Worktree plus container per agent** | Dagger's Container Use and DevTree combine worktrees with per-agent containers [7][8] | Emerging; the direct match for a container per worktree |

## Details that affect Caiman

- **Dev containers bind-mount the host repository** as the workspace, and
  recommend a named volume at `~/.claude` (with `CLAUDE_CONFIG_DIR`) because
  the container home is discarded on rebuild [1]. Transcripts are therefore
  usually not in a host folder.
- **Docker Sandboxes are microVMs, not containers.** Each has its own kernel and
  Docker engine. The workspace is mounted by filesystem passthrough at the same
  absolute path as on the host, with no sync step; other host directories are
  not reachable [3][9][10].
- **Container lifetimes vary.** Dev containers persist across stops but are
  recreated on rebuild [1]. Docker describes its sandboxes as disposable [3].
- **Claude Code's sandbox runtime** wraps the entire agent process, including
  hooks and MCP servers, in Seatbelt or bubblewrap, with configurable read and
  write rules [2].

## Conclusion

For a container per worktree, design for the agent inside the container. Treat
an agent on the host as the local setup, whether or not its toolchain is in a
container.

## Sources

1. [Development containers – Claude Code Docs](https://code.claude.com/docs/en/devcontainer)
2. [Choose a sandbox environment – Claude Code Docs](https://code.claude.com/docs/en/sandbox-environments)
3. [Docker Sandboxes: Run Claude Code and More Safely – Docker blog](https://www.docker.com/blog/docker-sandboxes-run-claude-code-and-other-coding-agents-unsupervised-but-safely/)
4. [Docker Sandboxes – product page](https://www.docker.com/products/docker-sandboxes/)
5. [ClaudeBox](https://github.com/RchGrav/claudebox)
6. [claude-container (host exec)](https://github.com/volkarts-dev/claude-container)
7. [Git Worktree Isolation Patterns – Zylos Research](https://zylos.ai/research/2026-02-22-git-worktree-parallel-ai-development/)
8. [Parallel Coding Agents with Container Use and Git Worktree](https://zazencodes.substack.com/p/parallel-coding-agents-with-container)
9. [Docker Sandboxes architecture – Docker Docs](https://docs.docker.com/ai/sandboxes/architecture/)
10. [Running AI agents safely in a microVM using docker sandbox – Andrew Lock](https://andrewlock.net/running-ai-agents-safely-in-a-microvm-using-docker-sandbox/)
