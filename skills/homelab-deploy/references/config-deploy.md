# Config Deploy Procedures

Config deploys change service configuration without rebuilding binaries.
Common cases: systemd unit changes, environment files, traefik routes, cron jobs.

## Config Types

### systemd Unit Files

```bash
# Edit/deploy the unit file
scp <service>.service root@<container>:/etc/systemd/system/<service>.service

# Reload and restart
systemctl daemon-reload
systemctl restart <service>
systemctl status <service>
```

IaC location: `goldblum/ansible/roles/<role>/templates/<service>.service.j2`

### Environment Files

```bash
# Deploy env file
scp <service>.env root@<container>:/etc/<service>/<service>.env

# Restart to pick up changes
systemctl restart <service>
```

IaC location: `goldblum/ansible/roles/<role>/templates/<service>.env.j2`

### Traefik Dynamic Config

Traefik routes are managed via goldblum Ansible:

- Template: `goldblum/ansible/roles/traefik_server/templates/dynamic/services.yml.j2`
- Deployed to: `/etc/traefik/dynamic/services.yml` on proxy.lan (CT 210)
- Traefik watches for changes — no restart needed

### Prometheus Scrape Config

- Template: `goldblum/ansible/roles/monitoring_server/templates/prometheus.yml.j2`
- Alert rules: `goldblum/ansible/roles/monitoring_server/templates/rules/`
- After deploy: `promtool check config /etc/prometheus/prometheus.yml`
- Reload: `curl -X POST http://localhost:9090/-/reload`

### Cron Jobs

- Deploy via Ansible `cron` module or template to `/etc/cron.d/`
- Verify: `crontab -l` or `ls /etc/cron.d/`

## Key Rule

ALWAYS update the goldblum Ansible role template FIRST, then deploy.
Never edit config directly on a container without updating IaC.
