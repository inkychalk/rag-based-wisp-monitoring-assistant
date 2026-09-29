---
id: P-03
type: playbook
incident_type: interference
applies_to_towers: [A, B, C]
last_reviewed: 2026-09-14
---
## Trigger
Several customers on one AP repeatedly disconnect and reconnect over tens of minutes, while the backhaul and other towers are fine.

## Typical log evidence
- Repeated wireless lines from the AP: "disconnected, extensive data loss" and "disconnected, signal strength" with low values.
- Some customers also show PPPoE "terminating... - peer is not responding" from CORE-RTR. Others flap on wireless only.
- Bursts, not a steady pattern; drops often come in clusters.

## Check first
1. Confirm the backhaul is stable and only one AP shows the pattern. If several APs are affected, go to the backhaul_down playbook.
2. Run /interface wireless registration-table print on the AP and compare signal levels. Good signal with data loss points to interference; low signal on one customer only points to that CPE.
3. If a single customer accounts for most drops, go to the chronic_customer approach instead.

## Isolate
4. Use /interface wireless frequency-monitor wlan1 (or a snooper, /interface wireless snoop wlan1) to see activity on the current channel and nearby ones.
5. Pick a cleaner channel from that view.

## Fix
6. Change the frequency with /interface wireless set wlan1 frequency=<clean value>. Expect all clients to reassociate briefly.
7. If no channel is clean, narrow the channel width and re-check.

## Verify
Watch /log print where topics~"wireless" for 30 minutes. Drops should stop and PPPoE sessions should stay up.

## Escalate
Send a person on site if drops continue on every available channel, or the AP itself looks unhealthy.

## Do not
Do not change the channel more than once in ten minutes. Do not touch the backhaul frequency to fix an AP problem.