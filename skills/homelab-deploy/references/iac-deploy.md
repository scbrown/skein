# IaC Deploy Procedures (Ansible)

Infrastructure changes go through Ansible roles in your infra repo. Everything below is
layout-generic — substitute your repo name and role names.

## Role Inventory

Keep an inventory like this in your infra repo README so an agent can map a service to a role
without guessing. Example shape:

| Role | Host | Purpose |
|------|------|---------|
| automation_server | app01 | ops MCP server, bots, issue tracker, bridges |
| bot_server | bot01 | chat bridges, message router |
| db_server | ${DB_HOST} | database, event daemon |
| monitoring_server | monitor01 | Prometheus, Alertmanager, Grafana, notifications |
| dashboard_server | app01 | status dashboard |
| traefik_server | proxy01 | reverse proxy, TLS |
| git_server | git.example.com | git hosting + CI runners |

## Running Ansible

```bash
# From your infra workspace
cd ~/workspace/infra

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

Secrets come from environment variables or a secret manager, NEVER hardcoded in playbooks:

- Database passwords, API tokens, bot tokens — all injected at run time
- Use a secret manager (Infisical, Vault, SOPS, …) for long-term storage

NEVER hardcode credentials in templates or task files. NEVER echo one into a log line.

## IaC Workflow

1. Edit the Ansible role (templates, tasks, defaults)
2. Commit to the infra repo
3. Run the playbook (or let CI trigger it)
4. Verify service health on the target host
5. Push the infra repo
