# Trusted Household User Mode

## Status

Trusted Household User Mode is the current local identity model for Project Anam.

This is not real authentication. It is a limited trust model for Lyle and Lyle's wife on a trusted home LAN or VPN.

## Purpose

Project Anam currently accepts `user_id` from the local client request body for chat, upload, and operator actions that need household source attribution. This keeps source labels useful while the project remains a private household system.

The goal of this mode is to reduce accidental wrong-user use and document the boundary clearly. It is not meant to defend against malicious clients on the same network.

## Current Identity Model

- Intended users are Lyle and Lyle's wife.
- Access is intended only on the trusted home LAN or through VPN.
- The frontend selects an active household user and sends that user's `user_id` to the backend.
- The backend uses `user_id` for source attribution, conversation ownership checks, artifact ownership checks, and related provenance.
- `user_id` is source attribution, not proof of identity.
- Anyone who can make API requests can supply another user's `user_id`.

This is acceptable only while Project Anam remains a trusted household/LAN/VPN system.

## Relationship To `ANAM_API_SECRET`

If configured, `ANAM_API_SECRET` protects non-public API routes with a shared secret.

That shared secret can reduce accidental or casual network access, but it does not provide per-user identity. It does not prove whether Lyle or Lyle's wife made a request. It is not a replacement for real login/session authentication.

## In Scope

Trusted Household User Mode should cover:

- clear documentation that the model is trusted-client identity
- visible active-user display in the UI
- source labels that preserve which household user supplied a conversation, message, or artifact
- local household/LAN/VPN use only
- conservative warnings for future contributors

Accidental wrong-user use is in scope for this mode.

## Out Of Scope

The following are not solved by Trusted Household User Mode:

- malicious household spoofing
- untrusted LAN clients
- public internet exposure
- guest access
- username/password login
- session cookies
- token-based user authentication
- OAuth or MFA
- per-user authorization policy

If someone trusted enough to access the home LAN/VPN intentionally crafts API requests to impersonate another household user, that is outside this v1 trust model and indicates a larger network or household trust problem.

## Required Before Broader Exposure

Real Login / Session Auth v1 is required before any of the following:

- public internet exposure
- guest access
- untrusted LAN access
- broader device/network deployment
- sensitive admin UI expansion

In the real auth model:

- the backend resolves user identity from an authenticated session or token
- the frontend no longer controls user identity directly
- body-trusted `user_id` is removed or ignored
- per-user authorization rules can be added explicitly

## Contributor Warning

Do not mistake the current `user_id` behavior for authentication.

It is a household source-attribution mechanism for a trusted local deployment, not a public or multi-tenant security boundary.
