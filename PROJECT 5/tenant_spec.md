# Formify Multi-Tenancy Architecture

## Isolation Strategy
Explain why you chose **Row-Level Security** vs. **Schema-per-Tenant**. 
(For this project, we are using Shared Schema, Row-Level Isolation).

## The Scoping Dependency
Describe how `get_org_db` works. How does it ensure a junior developer cannot accidentally write a "Global Query"?

## Performance & Indexing
List the composite indexes added to the database. 
Explain why `(org_id, id)` is better than just `(id)` in a multi-tenant system.

## Plan Enforcement (Stretch Goal)
How does the middleware calculate the current month's submissions for an Org before allowing a new write?