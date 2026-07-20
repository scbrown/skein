# Binary Deploy Procedures

Each service has a specific build-copy-restart flow. Always verify the service
is healthy BEFORE deploying (so you have a baseline) and AFTER.

## Service Registry

Keep a table like this one in your own IaC repo (`docs/service-catalog.yml` or equivalent) and
point this file at it. The rows below are an **example shape**, not a real fleet — replace them.

| Service | Repo | Host | Binary Path | Port | Health |
|---------|------|------|-------------|------|--------|
| search-api | example-org/search-api | node01 | /usr/local/bin/search-api | 3000 | /healthz |
| issues (cli) | example-org/issues | app01 | /usr/local/bin/issues | CLI | `issues version` |
| ops-mcp | example-org/ops-mcp | app01 | /opt/ops-mcp/ | 8090 | /health |
| dashboard | example-org/dashboard | app01 | /usr/local/bin/dashboard | 8070 | /healthz |
| eventd | example-org/eventd | ${DB_HOST} | /opt/eventd/ | 8075 | /health |
| chat-bridge | example-org/infra `deploy/` | bot01 | /opt/chat-bridge/ | 8099 | /health |
| message-router | example-org/infra `deploy/` | bot01 | /opt/message-router/ | 8070 | /health |

## Compiled Binary Deploy (Go, Rust, …)

```bash
# 1. Build locally
cd <worktree>
go build -o <binary> ./cmd/<name>
# or: GOOS=linux GOARCH=amd64 go build -o <binary> ./cmd/<name>

# 2. Copy to the host
scp <binary> root@<host>:/tmp/<binary>-new

# 3. Deploy on the host (over SSH, or via your ops MCP server)
systemctl stop <service>
cp <binary-path> <binary-path>.bak      # rollback point — do this BEFORE overwriting
cp /tmp/<binary>-new <binary-path>
chmod 755 <binary-path>
systemctl start <service>

# 4. Verify
systemctl is-active <service>
curl -sf http://localhost:<port>/healthz
```

## Interpreted Service Deploy (Python, Node, …)

```bash
# 1. Push code
git push

# 2. Pull on the host
cd /opt/<service> && git pull

# 3. Restart
systemctl restart <service>

# 4. Verify
systemctl is-active <service>
curl -sf http://localhost:<port>/health
```

## Services That Live In The Infra Repo

Some small services have their source inside the infra/ops repo itself, under
`deploy/<service>/`. The deploy flow is identical to the interpreted-service
flow above — only the source location differs.

## Rollback

If deploy fails:

1. Check logs: `journalctl -u <service> -n 50`
2. Compiled binary: restore the backup (`cp <binary-path>.bak <binary-path>`)
3. Interpreted: `git checkout HEAD~1` on the host
4. Restart the service
5. File an issue for the failed deploy with the error details
