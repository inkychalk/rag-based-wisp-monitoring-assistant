---
id: P-02
type: playbook
incident_type: power_failure
applies_to_towers: [A, B, C]
last_reviewed: 2026-09-14
---
## Trigger
A tower's BH and AP go silent together with no signal warnings first, or a device logs an unclean reboot after coming back.

## Typical log evidence
- CORE-RTR logs users on the tower ending with "peer is not responding".
- No wireless degradation lines from the tower before the drop.
- On return, TX-BH and TX-AP1 log "router was rebooted without proper shutdown, probably power failure". The two often come back within minutes of each other.

## Check first
1. Run /ppp active print and confirm all users on the tower are gone. If only one device is silent, go to step 5.
2. Ping the BH and the AP. Both silent points to site power; go to step 3.
3. Check the tower link port on CORE-RTR with /interface print. Port down alongside silent devices supports power loss on the PoE feed.

## Isolate
4. Ask on-call whether other sites lost power around the same time.
5. One device silent, other alive: suspect its injector or cable, not site power.

## Fix
6. When devices return, do not touch anything until both are up and logging.
7. Run /system resource print on each device and check uptime. Uptime matching across BH and AP means one shared power event.
8. If devices reboot repeatedly, escalate; there is no remote fix.

## Verify
Confirm users redial with /ppp active print. Check /log print where message~"rebooted" for a single event, not repeats.

## Escalate
Send a person on site if devices do not return within 30 minutes, reboot again within a day, or only one device returns.

## Do not
Do not assume power was the cause without evidence of a simultaneous loss. Do not push configuration changes to a device that has just rebooted until it has been stable.