<!--
PR template — Cross-SDK sync awareness.

Fill in a short summary of WHAT changed and WHY. Link the planning artifact
(`.planning/` PLAN-NN-... entry or issue number) that motivated this work.
-->

## Summary

<!-- 1-3 sentence description of what this PR does and why. Link the
     `.planning/` plan or issue this work resolves. -->

## Test plan

<!-- Bulleted checklist of how this was tested. Include any new fixtures,
     parity-test impact, or pre-publish verifications. -->

- [ ]

## Cross-SDK Sync (see [`.planning/CROSS-SDK-SYNC.md`](.planning/CROSS-SDK-SYNC.md))

If this PR touches the parity-trigger surface (see
[`.github/parity-trigger-paths.json`](.github/parity-trigger-paths.json)), ONE
of the following MUST be true:

- [ ] A paired-language change is included in this PR (Python + TS both updated)
- [ ] A parity ticket is filed and referenced below as `Parity-Ticket: #<num>`
- [ ] The change is intentionally one-language-only and labeled below as
      `python_only: true` or `typescript_only: true` with a one-sentence
      justification

<!-- Examples (uncomment and fill in the one that applies):

Parity-Ticket: #123
python_only: true — interim shim for mostly-light migration; no TS-side analog needed
typescript_only: true — UI helper specific to Chrome extension overlay

-->
