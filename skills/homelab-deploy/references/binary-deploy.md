# Binary Deploy Procedures

Each service has a specific build-copy-restart flow. Always verify the service
is healthy BEFORE deploying (so you have a baseline) and AFTER.

## Service Registry

| Service | Repo | Container | Binary Path | Port | Health |
|---------|------|-----------|-------------|------|--------|
| bobbin | YOUR_ORG/bobbin | tagi.lan (physical host) | /usr/local/bin/bobbin | 3000 | /healthz |
| beads (bd) | scbrown/beads | automation.lan (CT 205) | /usr/local/bin/bd | CLI | `bd version` |
| homelab-mcp | YOUR_ORG/homelab-mcp | automation.lan (CT 205) | /opt/homelab-mcp/ | 8090 | /health |
| tapestry | YOUR_ORG/tapestry | tapestry.lan (CT 227) | /usr/local/bin/tapestry | 8070 | /healthz |
| reactor | YOUR_ORG/reactor | ${DB_HOST} (CT 236) | /opt/reactor/ | 8075 | /health |
| aegis-irc | aegis deploy/ | bot.lan (CT 201) | /opt/aegis-irc/ | 8099 | /health |
| aegis-tg | aegis deploy/ | automation.lan (CT 205) | /opt/aegis-tg/ | 8071 | /health |
| message-router | aegis deploy/ | bot.lan (CT 201) | /opt/message-router/ | 8070 | /health |

## Go Binary Deploy (bobbin, tapestry, beads)

```bash
# 1. Build locally
cd <worktree>
go build -o <binary> ./cmd/<name>
# or: GOOS=linux GOARCH=amd64 go build -o <binary> ./cmd/<name>

# 2. Copy to container
scp <binary> root@<container>:/tmp/<binary>-new

# 3. Deploy on container (via MCP batch_probe or SSH)
systemctl stop <service>
cp /tmp/<binary>-new <binary-path>
chmod 755 <binary-path>
systemctl start <service>

# 4. Verify
systemctl is-active <service>
curl -sf http://localhost:<port>/healthz
```

## Python Service Deploy (homelab-mcp, reactor, aegis-tg)

```bash
# 1. Push code to git.svc
git push

# 2. Pull on container (via MCP batch_probe)
cd /opt/<service> && git pull

# 3. Restart
systemctl restart <service>

# 4. Verify
systemctl is-active <service>
curl -sf http://localhost:<port>/health
```

## Deploy Artifacts in aegis (aegis-irc, message-router, aegis-tg)

These services have source code in the aegis repo under `deploy/<service>/`.
The deploy flow is the same as Python services but source is in aegis, not
a separate repo.

## Rollback

If deploy fails:

1. Check logs: `mcp__homelab__container_logs` or `journalctl -u <service> -n 50`
2. If binary deploy: restore backup (`cp <binary>.bak <binary-path>`)
3. If Python: `git checkout HEAD~1` on container
4. Restart service
5. File a bead for the failed deploy with error details
