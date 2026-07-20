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
- [ ] Metrics scraping? (`up{job="<service>"}` should be 1)
