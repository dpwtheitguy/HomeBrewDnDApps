# Weapon playability audit

5,617 weapon records scanned. Structural errors affect 0 records. Content review is queued for 4,502 records.

Scope is catalog records indexed with type weapon. Ammunition indexed separately has its own field audit. This scan checks weapon fields, profile references, BG3 variant structure, and positive prices. Full catalog schema validation is a separate check. Drafts, original game statistics, and base weapon comparisons retain their own evidence labels.

## Rules evidence

| Evidence | Records |
|---|---:|
| base-weapon-draft | 3,229 |
| improvised-fallback | 636 |
| native-bg3 | 428 |
| published-2024-structured | 267 |
| published-2024-reference | 212 |
| published-2024-cross-reference | 206 |
| upgrade-dependent | 170 |
| item-specific-draft | 135 |
| verified-2024-enhancement | 96 |
| reference-object | 65 |
| published-2024-attack | 62 |
| launcher-dependent | 51 |
| verified-2024-ordinary-weapon | 36 |
| verified-2024-enhancement-with-base-note | 12 |
| source-variant-conflict | 10 |
| source-based-2024 | 1 |
| verified-2024-adventuring-gear | 1 |

## Largest review queues

| Source | Records with a gap |
|---|---:|
| conan-exiles-reference | 971 |
| diablo-2-reference | 387 |
| dmg-35-reference | 251 |
| dndbeyond-public-index | 223 |
| mystara-fan-names-reference | 223 |
| open5e-vom | 222 |
| baldurs-gate-1-reference | 214 |
| diablo-3-reference | 194 |
| arms-equipment-3e-reference | 190 |
| nioh-2-reference | 190 |
| baldurs-gate-2-reference | 174 |
| dmg-2e-reference | 151 |
| adventurers-vault-1-reference | 143 |
| planescape-torment-reference | 115 |
| diablo-4-reference | 74 |

## Structural errors

0 weapon profiles point to a missing or non-weapon catalog record.


The [weapon playability CSV](weapon-playability.csv) contains each record and its evidence fields.
A blank field can mean that the cited rules are prose-only, the field is inapplicable, or the information is unresolved.
