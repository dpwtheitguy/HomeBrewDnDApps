# Weapon playability audit

5,616 weapon records scanned. Structural errors affect 0 records. Content review is queued for 4,201 records.

Scope is catalog records indexed with type weapon. Ammunition indexed separately has its own field audit. This scan checks weapon fields, profile references, BG3 variant structure, and positive prices. Full catalog schema validation is a separate check. Drafts, original game statistics, and base weapon comparisons retain their own evidence labels.

## Rules evidence

| Evidence | Records |
|---|---:|
| base-weapon-draft | 2,389 |
| item-specific-draft | 1,158 |
| native-bg3 | 428 |
| improvised-fallback | 408 |
| published-2024-attack | 355 |
| published-2024-reference | 256 |
| published-2024-structured | 222 |
| published-2024-cross-reference | 122 |
| verified-2024-enhancement | 96 |
| reference-object | 65 |
| launcher-dependent | 48 |
| verified-2024-ordinary-weapon | 36 |
| verified-2024-enhancement-with-base-note | 12 |
| documented-reference | 8 |
| item-specific-siege-draft | 6 |
| upgrade-dependent | 5 |
| source-based-2024 | 1 |
| verified-2024-adventuring-gear | 1 |

## Largest review queues

| Source | Records with a gap |
|---|---:|
| conan-exiles-reference | 971 |
| diablo-2-reference | 387 |
| open5e-vom | 227 |
| mystara-fan-names-reference | 223 |
| baldurs-gate-1-reference | 214 |
| diablo-3-reference | 194 |
| arms-equipment-3e-reference | 190 |
| nioh-2-reference | 190 |
| dmg-35-reference | 180 |
| baldurs-gate-2-reference | 174 |
| adventurers-vault-1-reference | 143 |
| dndbeyond-public-index | 133 |
| planescape-torment-reference | 115 |
| dmg-2e-reference | 108 |
| diablo-4-reference | 74 |

## Structural errors

0 weapon profiles point to a missing or non-weapon catalog record.


The [weapon playability CSV](weapon-playability.csv) contains each record and its evidence fields.
A blank field can mean that the cited rules are prose-only, the field is inapplicable, or the information is unresolved.
