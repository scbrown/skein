---
name: homelab-deploy
description: >
  Deploy homelab services. Use this skill when asked to "deploy", "ship",
  "push to production", "update service", "release binary", "roll out",
  or when deploying any homelab service to a host or container. Covers binary
  builds, config changes, and Ansible IaC runs. Activates on any deploy-related
  intent in an operations context.
---

# Deploy Skill

Homelab deploys fall into three categories. Identify which one before acting.

**Stack tools this reaches for**

| Present | This skill uses it for | Absent — what happens |
|---|---|---|
| **[hank](https://github.com/scbrown/hank)** | `hank impact <symbol>` — what a code change actually reaches, before you ship it | you deploy on a guess about blast radius, or read the call graph by hand |
| **[bobbin](https://github.com/scbrown/bobbin)** | `bobbin search` / `bobbin related` — find the config and the coupled files you'd otherwise miss | `grep`, and whatever you forget isn't in the diff |
| **[metrics-query](../metrics-query/SKILL.md)** | the post-deploy verify — `up`, error rate, restart count | `curl` the health endpoint once and hope |
| **[quipu](../quipu/SKILL.md)** | what depends on this service, and what broke last time | deploy without the dependency map |
| **[notify](../notify/SKILL.md)** | telling someone it shipped, or didn't | say it wasn't sent |

## Know the blast radius before you build

A deploy is a change to a running system, and the expensive part is never the
copy — it is the thing downstream you did not know was downstream.

```bash
hank impact <symbol>            # symbols transitively affected by changing this
hank impact <symbol> --json     # same, machine-readable
bobbin related <path>           # files that historically change WITH this one
bobbin review                   # review context assembled from the git diff
```

`hank impact` reads the call graph; `bobbin related` reads *git history*, and
they disagree in the interesting cases — a config file and a template that always
change together have no import edge between them. **Two different kinds of
coupling, and the one that bites is usually the one with no edge in the code.**
Then ask [quipu](../quipu/SKILL.md) what depends on the *service*, which neither
of them can see.

If you don't have these, say so in the deploy notes rather than implying you
checked. "I did not verify blast radius" is a useful sentence; silence is not.

## Category Decision Tree

1. **Did source code change?** (Go, Python, Rust, etc.)
   -> Binary deploy. Read `references/binary-deploy.md`.

2. **Did config change?** (systemd unit, env file, proxy rule, cron)
   -> Config deploy. Read `references/config-deploy.md`.

3. **Is this infrastructure?** (new container, user, package, Ansible role)
   -> IaC deploy. Read `references/iac-deploy.md`.

If unsure, check the issue description or recent commits to determine what changed.

## Before You Deploy

Always gather live state first. Do NOT assume — verify:

```bash
systemctl is-active <service>              # is it running right now?
systemctl show <service> -p ActiveEnterTimestamp
journalctl -u <service> -n 50 --no-pager   # errors BEFORE you deploy
```

If you have an ops MCP server, its tools are the faster path to the same facts
(e.g. `service_health`, `container_status`, `container_logs`). The shell above is
the fallback that always works — the skill never depends on the MCP server.

Check which host runs the service:

- `git remote -v` in the service repo tells you the source
- Service catalog: `docs/service-catalog.yml` (if you keep one)
- Example mappings are in `references/binary-deploy.md`

## Deploy Invariants (NEVER skip these)

1. **IaC-first**: Every deploy MUST be reflected in your Ansible roles.
   Deploy code AND update IaC in the SAME session. No cowboy deploys.

2. **Verify after deploy**: Always confirm the service is healthy post-deploy.
   Curl the health endpoint — don't infer health from "the command exited 0".

3. **Commit both repos**: If you changed code in one repo and IaC in another,
   commit and push BOTH before ending the session.

4. **No stale state**: Query live host state, don't rely on cached info.

5. **Heredoc quoting**: When deploying via SSH heredoc, ALWAYS use single-quoted
   delimiters (`<< 'EOF'`, not `<< EOF`). An unquoted heredoc expands `$` and
   backticks on the *sending* side and will corrupt shebangs and config values —
   silently, and the file will still look plausible.

## Post-Deploy Checklist

- [ ] Service running? (`systemctl is-active <service>`)
- [ ] Health endpoint responding? (`curl -sf http://<host>:<port>/healthz`)
- [ ] Logs clean? (no panics, no errors in last 30s)
- [ ] IaC updated? (the Ansible role reflects what you actually deployed)
- [ ] Metrics scraping? (`promq.py query 'up{job="<service>"}'` — see below)

### Verifying with metrics, without fooling yourself

```bash
python3 ../metrics-query/promq.py query 'up{job="<service>"}'    # side-by-side install
curl -sG "${PROM_URL}/api/v1/query" --data-urlencode 'query=up{job="<service>"}'   # or raw
```

Three traps sit exactly here, on the happy path, right when you want to be done:

- **Exit `2` (EMPTY) is not a pass.** A typo in the job label returns no series
  over HTTP 200 — which is also what a job that was never scraped returns. If the
  selector matches nothing, you have verified nothing.
- **An instant query is up to 5 minutes stale.** Immediately after a deploy, `up`
  may still be answering from a sample taken *before* you shipped. Either wait a
  scrape interval or read `promq.py targets` for the actual last-scrape state.
- **`up == 1` means the exporter answered, not that the service works.** A wedged
  app with a live `/metrics` endpoint scrapes perfectly forever.

Curl the real health endpoint too, and don't infer health from "the command
exited 0".
