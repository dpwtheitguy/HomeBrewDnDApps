# Mystara regional and expedition expansion

This pass adds **25 selected project drafts**, including regional reskins, travel tools, lesser Alphatian magic and two original skyship proposals. These extend the existing Mystara pack rather than duplicate its eleven earlier Atruaghin/Thyatian entries.

- **Champions of Mystara: Heroes of the Princess Ark**: Hero’s Journal, Explorer’s Manual and Designer’s Manual each have an original-source audit queued. Fourteen fan-index skyship leads are retained separately and do not inflate item counts. The two crewed skyship proposals are new designs, not the Princess Ark’s canonical statistics. No space/plane travel, weapon system or complete skyship-construction engine is implied.
- **Dawn of the Emperors**: selected Thyatian gladius, pugio, pilum, scutum and uniform references; Alphatian court clothing and lesser fan-inspired library/messaging gear. Fan expansions remain labeled as such.
- **GAZ14: The Atruaghin Clans**: the five scopes are **Bear, Horse, Elk, Turtle and Tiger**. The earlier false Children of the Buffalo tag has been removed from taxonomy, queue and shield attribution. The Buffalo Hide Shield has broad Atruaghin attribution only; its specific clan is not established by that reference. Existing Eagle Lance and other explicitly reported clan items now have typed clan associations.

The fictional Atruaghin clans do not stand in for interchangeable real Indigenous nations. Source depictions do not create ancestry-based proficiency, alignment, technology limits or mandatory behavior in the 2024 data.

Three explicitly fictional campaign proposals draw on different game contexts:

- **Never Alone / Kisima Ingitchuna**: the official page attests its bola. The Plateau Trail Bola is a new, bounded Atruaghin-compatible design; it is not Nuna’s canonical weapon statistics or an authentic Iñupiat artifact.
- **Mulaka**: Lienzo’s developer material supplies a distinct Rarámuri context. The runner’s sandals are a project invention inspired by terrain/travel play, not an attested game item or ceremonial object.
- **When Rivers Were Trails**: creator-described Indigenous travel and cooperation themes inform an ordinary rope proposal. No Anishinaabe ceremonial material or historical artifact is being presented as generic loot.

Each record’s `research_metadata` and `provenance.adaptation_note` distinguish actual source-item evidence from broader thematic inspiration. Original book mechanics and cultural details remain pending review.

```sh
python3 scripts/search_catalog.py --culture Thyatian
python3 scripts/search_catalog.py --culture Alphatian
python3 scripts/search_catalog.py --culture 'Atruaghin Horse Clan'
python3 scripts/search_catalog.py --origin 'Champions of Mystara' --relationship inspired-by
```
