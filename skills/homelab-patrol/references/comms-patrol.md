# Comms Patrol Reference

For ellie and comms-focused agents.

## Comms Service Checklist

| Service | Container | Port | Check |
|---------|-----------|------|-------|
| aegis-irc | bot.lan (211) | 8099 | `service_health bot.lan aegis-irc` |
| message-router | bot.lan (211) | 8070 | `service_health bot.lan message-router` |
| aegis-tg | automation (215) | 8071 | `service_health automation aegis-tg` |
| reactor | ${DB_HOST} (236) | 8075 | `service_health ${DB_HOST} reactor` |
| ntfy | monitoring (212) | 8080 | `service_health monitoring ntfy` |
| approval-bridge | automation (215) | 5070 | `service_health automation approval-bridge` |

## Message Delivery Verification

Test the full delivery chain:

1. IRC -> aegis-irc -> message-router -> target
2. Telegram -> aegis-tg -> message-router -> target
3. Reactor event -> message-router -> IRC + Telegram

## Prometheus Queries for Comms

```promql
# Message router throughput (if metrics exported)
rate(messages_routed_total[5m])

# IRC connection status
up{job="aegis-irc"}

# Reactor event processing
up{job="reactor"}
```

## Common Issues

- **aegis-tg polling conflict**: Only one process can call getUpdates.
  If approval-bridge also polls, one will fail. Check for "terminated by
  other getUpdates" in logs.
- **IRC reconnect**: ergo (IRC server) occasionally drops connections.
  aegis-irc should auto-reconnect. Check logs for reconnect loops.
- **message-router routing**: Messages to unknown channels get dropped.
  Check `message_router_status` MCP tool for active routes.
