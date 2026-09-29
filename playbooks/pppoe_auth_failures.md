---
id: P-04
type: playbook
incident_type: pppoe_auth_failures
applies_to_towers: [A, B, C]
last_reviewed: 2026-09-14
---
## Trigger
A group of customers cannot connect and retry repeatedly, usually after a profile or secret change on CORE-RTR. Wireless is healthy.

## Typical log evidence
- CORE-RTR logs "authentication failed" under pppoe,ppp,error, repeating for each affected user about once a minute.
- No matching wireless disconnects on the AP.
- The users do not appear in /ppp active print.
- Once fixed, "authenticated" and "connected" follow.

## Check first
1. Run /log print where topics~"pppoe" and list which users fail. If failures follow a recent edit, note the time; go to step 3.
2. If failures span all towers, check the RADIUS or authentication source, or CORE-RTR itself, before individual secrets.
3. Check the secrets with /ppp secret print and the profile with /ppp profile print.

## Isolate
4. Compare a failing secret against a working one: password, profile, service and any address settings.
5. If secrets match but users still fail, check the address pool with /ip pool print for exhaustion.

## Fix
6. Reset the affected passwords from the customer records and re-apply the correct profile with /ppp secret set.
7. Ask customers to power-cycle the CPE only if it keeps the old password cached.

## Verify
Confirm the users appear in /ppp active print and the "authentication failed" lines stop.

## Escalate
Escalate if failures continue after the secrets are corrected, or if the error affects users who were not edited.

## Do not
Do not edit secrets in bulk again to fix a bulk edit. Do not disable authentication, even temporarily.