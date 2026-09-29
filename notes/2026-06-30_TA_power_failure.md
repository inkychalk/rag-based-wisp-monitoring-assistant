---
id: N-2026-0630-01
type: incident
date: 2026-06-30
tower: A
devices: [TA-BH, TA-AP1, CORE-RTR]
incident_type: power_failure
severity: critical
customers_affected: 15
duration_min: 21
root_cause_status: not_confirmed
key_incident_id: none
---
## Symptom
Tower A vanished at 21:12 on a Tuesday evening. All 15 customers lost their session. TA-BH and TA-AP1 went silent, then both came back at about 21:33 reporting an unclean reboot. About 21 min. Sessions redialled over the next few minutes.

## Evidence
CORE-RTR saw the sessions end, then nothing from Tower A devices:

    Jun 30 21:12:08 CORE-RTR pppoe,ppp,info <pppoe-cust-A004>: terminating... - peer is not responding

First lines back:

    Jun 30 21:33:30 TA-BH system,error,critical router was rebooted without proper shutdown, probably power failure
    Jun 30 21:33:41 TA-AP1 system,error,critical router was rebooted without proper shutdown, probably power failure

There were no signal warnings and no wireless lines before the drop.

## Root cause
Not confirmed. Both devices lost power at the same moment, but the log cannot tell us why. Candidates:
1. A commercial power cut in the area around the tower.
2. A failing PSU or PoE injector in the tower cabinet.
3. A tripped breaker at the site.

## Fix
None. Power returned by itself.

## Verification
/ppp active print where name~"cust-A" showed 15 sessions again shortly after 21:35.

## Follow-up
Nobody has been on site yet. Ask whether the neighbours lost power that evening. If it happens again, note which of the two devices logs the reboot first.