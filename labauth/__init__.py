"""labauth: the accounts, communities and permissions shared by Home, Admin, Shopping, Nyochi and later house apps.

The canonical copy lives in the `home` repo; `home/scripts/sync_labauth.sh` copies it into the other apps. Only Home
runs its migrations (on the lab-auth database); the other apps read and write the same tables. Every app checks on its
first request that its copy knows the same migrations as the database (`checks.schema_problem`).

Files:
  catalogue.py   the permission codes, grouped by app (Admin draws its grid from it)
  models.py      Community, Membership, CommunityGrant, MemberGrant, Invite, PlatformGrant, AuditEntry, AuthAttempt
  access.py      who has which permission in which community (the one place that decides)
  rules.py       who may change what in Admin (roles, grants, members)
  middleware.py  request.community / request.membership / request.perms, and the per-app access gate
  scope.py       community_rows() / personal_rows(): the data an app shows in the active community
"""
