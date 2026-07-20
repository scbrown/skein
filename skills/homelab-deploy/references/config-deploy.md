# Config Deploy Procedures

Config deploys change service configuration without rebuilding binaries.
Common cases: systemd unit changes, environment files, reverse-proxy routes, cron jobs.

Paths below assume an Ansible IaC repo laid out as `ansible/roles/<role>/…`. Substitute your own.

## Config Types

### systemd Unit Files

```bash
# Edit/deploy the unit file
scp <service>.service root@<host>:/etc/systemd/system/<service>.service

# Reload and restart
systemctl daemon-reload
systemctl restart <service>
systemctl status <service>
```

IaC location: `ansible/roles/<role>/templates/<service>.service.j2`

### Environment Files

```bash
# Deploy env file
scp <service>.env root@<host>:/etc/<service>/<service>.env

# Restart to pick up changes
systemctl restart <service>
```

IaC location: `ansible/roles/<role>/templates/<service>.env.j2`

### Reverse Proxy (Traefik) Dynamic Config

- Template: `ansible/roles/traefik_server/templates/dynamic/services.yml.j2`
- Deployed to: `/etc/traefik/dynamic/services.yml` on the proxy host
- Traefik watches the file for changes — no restart needed

### Prometheus Scrape Config

- Template: `ansible/roles/monitoring_server/templates/prometheus.yml.j2`
- Alert rules: `ansible/roles/monitoring_server/templates/rules/`
- After deploy: `promtool check config /etc/prometheus/prometheus.yml`
- Reload: `curl -X POST http://localhost:9090/-/reload`

### Cron Jobs

- Deploy via the Ansible `cron` module, or template into `/etc/cron.d/`
- Verify: `crontab -l` or `ls /etc/cron.d/`
- **Never** pipe into `crontab -` without preserving what's there:
  `(crontab -l; echo "<new line>") | crontab -`

## Key Rule

ALWAYS update the IaC role template FIRST, then deploy.
Never edit config directly on a host without updating IaC — the next playbook run
will silently revert you, and you will debug the wrong thing.
