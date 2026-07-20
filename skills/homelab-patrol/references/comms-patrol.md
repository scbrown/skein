# Comms Patrol Reference

For comms-focused agents: chat bridges, message routing, event delivery.

## Comms Service Checklist

Example fleet — substitute your own.

| Service | Host | Port | Check |
|---------|------|------|-------|
| irc-bridge | bot01 | 8099 | `systemctl is-active irc-bridge` |
| message-router | bot01 | 8070 | `systemctl is-active message-router` |
| telegram-bridge | app01 | 8071 | `systemctl is-active telegram-bridge` |
| eventd | ${DB_HOST} | 8075 | `systemctl is-active eventd` |
| notifications (ntfy) | monitor01 | 8080 | `systemctl is-active ntfy` |
| approval-bridge | app01 | 5070 | `systemctl is-active approval-bridge` |

## Message Delivery Verification

Test the full delivery chain — end to end, not per-hop:

1. IRC -> irc-bridge -> message-router -> target
2. Telegram -> telegram-bridge -> message-router -> target
3. Event -> message-router -> IRC + Telegram

**A hop that reports 200 is not a delivered message.** Send a real test message
and confirm it arrives at the far end. "Accepted by the server" and "read by a
human" are different facts, and only one of them is the one you care about.

## Prometheus Queries for Comms

```promql
# Message router throughput (if metrics exported)
rate(messages_routed_total[5m])

# Bridge connection status
up{job="irc-bridge"}

# Event processing
up{job="eventd"}
```

## Common Issues

- **Telegram polling conflict**: only one process may call `getUpdates` for a
  given bot token. If a second service also polls, one will fail. Look for
  "terminated by other getUpdates" in the logs.
- **IRC reconnect loops**: IRC servers drop connections routinely; the bridge
  should auto-reconnect. Check the logs for a *loop* — reconnecting forever is a
  different failure from reconnecting once.
- **Silent drops**: messages to unknown channels/routes are usually dropped
  without an error. Check the router's active route table, not just its uptime.
- **LAN-only notification transports**: a push server reachable only from inside
  the network cannot alert a phone that is outside it. Verify delivery from where
  the human actually is.
