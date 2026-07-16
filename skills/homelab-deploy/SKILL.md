---
name: homelab-deploy
description: >
  Deploy homelab services. Use this skill when asked to "deploy", "ship",
  "push to production", "update service", "release binary", "roll out",
  or when deploying any homelab service to a container. Covers binary builds,
  config changes, and Ansible IaC runs. Activates on any deploy-related intent
  in the homelab context.
---

# Deploy Skill

Homelab deploys fall into three categories. Identify which one before acting.

## Category Decision Tree

1. **Did source code change?** (Go, Python, Rust, etc.)
   -> Binary deploy. Read `references/binary-deploy.md`.

2. **Did config change?** (systemd unit, env file, nginx/traefik rule, cron)
   -> Config deploy. Read `references/config-deploy.md`.

3. **Is this infrastructure?** (new container, user, package, Ansible role)
   -> IaC deploy. Read `references/iac-deploy.md`.

If unsure, check the bead description or recent commits to determine what changed.

## Before You Deploy

Always gather live state first. Do NOT assume — verify:

```text
mcp__homelab__service_health  — Is the service currently running?
mcp__homelab__container_status — Container uptime, IP, hostname
mcp__homelab__container_logs   — Recent logs (check for errors before deploy)
```

Check which container hosts the service:

- `git remote -v` in the service repo tells you the source
- Service catalog: `docs/service-catalog.yml` (if available)
- Common mappings are in `references/binary-deploy.md`

## Deploy Invariants (NEVER skip these)

1. **IaC-first**: Every deploy MUST be reflected in goldblum Ansible roles.
   Deploy code AND update IaC in the SAME session. No cowboy deploys.

2. **Verify after deploy**: Always confirm the service is healthy post-deploy.
   Use `mcp__homelab__service_health` or curl the health endpoint.

3. **Commit both repos**: If you changed code in one repo and IaC in goldblum,
   commit and push BOTH before ending the session.

4. **No stale state**: Query live container state, don't rely on cached info.

5. **Heredoc quoting**: When deploying via SSH heredoc, ALWAYS use single-quoted
   delimiters (`<< 'EOF'` not `<< EOF`). Unquoted heredocs corrupt shebangs.

## Post-Deploy Checklist

- [ ] Service running? (`systemctl is-active <service>`)
- [ ] Health endpoint responding? (`curl -sf http://<host>:<port>/healthz`)
- [ ] Logs clean? (no panics, no errors in last 30s)
- [ ] IaC updated in goldblum? (ansible role reflects what you deployed)
- [ ] Prometheus scraping? (`up{job="<service>"}` should be 1)
