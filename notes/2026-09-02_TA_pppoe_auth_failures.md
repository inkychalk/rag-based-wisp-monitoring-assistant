---
id: N-2026-0902-01
type: incident
date: 2026-09-02
tower: A
devices: [CORE-RTR]
incident_type: pppoe_auth_failures
severity: major
customers_affected: 4
duration_min: 81
root_cause_status: confirmed
key_incident_id: none
---
## Symptom
Four Tower A customers could not get a PPPoE session back after a profile change on CORE-RTR at about 17:18: cust-A003, cust-A007, cust-A010, cust-A012. Each retried roughly once a minute and failed, from 17:20:14 until the fix at 18:41:37. About 81 min. Everyone else on Tower A was fine.

## Evidence
Wireless was healthy and the APs were quiet. Only the auth errors on the core:

    Sep 02 17:20:14 CORE-RTR pppoe,ppp,error <pppoe-cust-A007>: authentication failed
    Sep 02 17:21:15 CORE-RTR pppoe,ppp,error <pppoe-cust-A007>: authentication failed
    Sep 02 18:41:37 CORE-RTR pppoe,ppp,info <pppoe-cust-A007>: authenticated

## Root cause
The bulk edit that changed the profile also rewrote the password field on those four secrets.

## Fix
Checked the secrets with /ppp secret print where name~"cust-A", then reset the passwords from the customer records and re-applied the profile, for example /ppp secret set [find name="cust-A007"] profile=wisp-10m.

## Verification
/ppp active print showed all four users again by 18:43.

## Follow-up
cust-A012 called again the next day. Not clear whether that was the CPE holding an old password. Not checked.