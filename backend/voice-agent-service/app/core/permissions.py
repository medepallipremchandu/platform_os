"""Permission code constants this service checks against the `permissions` claim of a verified
iam-service access token. These strings must match iam-service's seeded catalog exactly - they
are not derived or guessed, they are looked up 1:1 against that source of truth (verify with
GET http://localhost:8003/permissions).
"""

PROVIDERS_MANAGE = "talentos.voiceagent.providers.manage"
PROVIDERS_READ = "talentos.voiceagent.providers.read"
CALLAGENTS_READ = "talentos.voiceagent.callagents.read"
CALLAGENTS_WRITE = "talentos.voiceagent.callagents.write"
CALLS_READ = "talentos.voiceagent.calls.read"
CALLS_WRITE = "talentos.voiceagent.calls.write"
