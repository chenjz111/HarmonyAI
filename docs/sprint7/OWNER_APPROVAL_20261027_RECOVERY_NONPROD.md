# Owner decision: nonproduction feedback recovery candidate

On 2026-10-27 the Owner explicitly approved design and tests for a nonproduction candidate using minimal operation metadata and an authenticated read-only recovery query, excluding feedback answers and access/refresh tokens from ordinary storage. This does not approve final data-retention or backup policy, deployment, production flags, or a new protected-page SHA. This independent record preserves the earlier Owner decisions.

The candidate must continue to treat absent records and unresolved in-flight transactions as unknown. A matching record without the original body or a safely verified original fingerprint must not be presented as proof of the exact original submission. Device storage durability, corruption, identity changes, expired Guest and uninstall require explicit safe handling and actual platform validation. The current internal-only read service is not a public route, and no durable client journal exists yet.
