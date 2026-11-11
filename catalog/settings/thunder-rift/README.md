# Thunder Rift and related boxed-adventure research

This first pass contains **9 original 2024 conversion drafts**, **9 source appearances linked to existing SRD definitions**, and **9 additional fan-index item leads**. Appearances and leads do not increase item-definition counts. JSON and YAML are supplied together.

- Zanzer: three drafts and nine existing-item mappings, using Kyle Knight’s explicitly merged and modified fan compilation. Physical PDF page numbers identify this compilation, not the original TSR book. Robes and powder on page 5 were visually checked.
- The Goblin’s Lair: publisher preview confirms Red Hand Trail, Trouble Below and Palace of Dread. The owlbear ring is only an OCR search lead; its new Accord draft grants charm rather than full control.
- The Haunted Tower: component adventures and selected item leads from Kyle Knight’s fan index. Two original drafts: Academy Healer’s Shield and Staff of the Stillwater Watch.
- The Dragon’s Den: same fan-index evidence level. Two original drafts: Otterkin Diver’s Staff and Red Serpent Firegoad. Otterkin maker attribution remains unverified.
- Hail the Heroes: Mystara / Karameikos / AD&D 2e; one lesser Shield of Halav echo inspired by fan lore. It is not the canonical artifact.
- Night of the Vampire: Mystara / Karameikos / AD&D 2e; bibliography checked; one existing Longsword +1 appearance is reported by a 3e fan conversion. This is not original AD&D-page verification; original item audit remains pending.

`adventure-pack.json` holds references, entities, drafts, appearances and leads. `research-queue.json` tracks the six workstreams and their component adventures. The shared builder imports drafts and associations; no adventure text or official artwork is distributed.

Thunder Rift is a separate setting filter. Grouping Zanzer and Dragon’s Den with it is editorial and follows fan research practice; it does not prove canonical placement within Thunder Rift or Karameikos. Publication facets are separate from geographic and cultural origin. For example:

```sh
python3 scripts/search_catalog.py --setting 'Thunder Rift'
python3 scripts/search_catalog.py --origin 'The Haunted Tower' --relationship inspired-by
python3 scripts/search_catalog.py --origin 'Zanzars Dungeon' --relationship found-in
```

Each draft has TLDR, full mechanics, original flavor, creative-use caveats, a reusable type icon and an explicitly estimated modern value. Modern prices are not legacy treasure totals. All drafts require DM review and playtesting. None supplies fully executable game effects yet.

Next: verify the three Haunted Tower adventures and three Dragon’s Den adventures against accessible item-specific sources; then Night of the Vampire and remaining Hail the Heroes content. Do not confuse the Haunted Tower box with unrelated adventures titled Haunted Tower, or the TSR Goblin’s Lair box with modern same-name homebrew.
