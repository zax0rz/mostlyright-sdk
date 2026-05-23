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

<!-- Examples (copy ONE outside this comment block and fill in real values):

```
Parity-Ticket: #<NUM>
python_only: <true_or_false> — <one-sentence reason if true>
typescript_only: <true_or_false> — <one-sentence reason if true>
```

The parity-gate parser strips HTML comments AND fenced code blocks before
matching, so these examples are inert in either form. The numeric/boolean
placeholders above (`<NUM>`, `<true_or_false>`) ALSO fail the regex on their
own — defense in depth against accidental copy-paste bypass.
-->
