# IaC Deploy Procedures (Ansible via goldblum)

Infrastructure changes go through Ansible roles in the goldblum repo.

## Goldblum Role Inventory

| Role | Container | Purpose |
|------|-----------|---------|
| automation_server | CT 205 (automation.lan) | homelab-mcp, aegis-tg, beads, approval-bridge |
| bot_server | CT 201 (bot.lan) | aegis-irc, message-router |
| dolt_server | CT 236 (${DB_HOST}) | Dolt DB, reactor |
| monitoring_server | CT 202 (monitoring.lan) | Prometheus, Alertmanager, Grafana, ntfy |
| tapestry_server | CT 227 (tapestry.lan) | Tapestry dashboard |
| traefik_server | CT 221 (traefik.lan) | Reverse proxy, TLS |
| forgejo_server | CT 206 (git.lan) | Forgejo git hosting |
| hla_server | CT 228 (DECOMMISSIONED) | HLA — migrated to Garage S3 |

## Running Ansible

```bash
# From goldblum workspace
cd ~/workspace/goldblum

# Run a specific role
ansible-playbook -i inventory/hosts site.yml --tags <role-name>

# Or limit to a specific host
ansible-playbook -i inventory/hosts site.yml --limit <hostname>

# Dry run first
ansible-playbook -i inventory/hosts site.yml --tags <role-name> --check --diff
```

## Role Structure

```text
ansible/roles/<role>/
  defaults/main.yml     # Default variables
  tasks/main.yml        # Task definitions
  templates/            # Jinja2 templates (.j2)
  files/                # Static files
  handlers/main.yml     # Restart/reload handlers
```

## Secrets

Secrets come from environment variables, NOT hardcoded in playbooks:

- `DOLT_ROOT_PASSWORD`, `DOLT_BEADS_PASSWORD`, `DOLT_TAPESTRY_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- Infisical for long-term secret storage

NEVER hardcode credentials in templates or task files.

## IaC Workflow

1. Edit the Ansible role (templates, tasks, defaults)
2. Commit to goldblum repo
3. Run playbook (or let CI trigger it)
4. Verify service health on target container
5. Push goldblum repo
