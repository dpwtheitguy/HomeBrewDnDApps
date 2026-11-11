# Continuing source audits

The current additional source-reference pass includes:

- Planescape: Torment selected inventory tables. This is not a full tabletop Planescape boxed-set import.
- Curse of Strahd: seven distinctive item/book names; original adventure, ordinary treasure and modified chapter items remain unaudited.
- Tomb of Annihilation: seven distinctive magic-item names. Chultan gear, transport, story treasures and chapter variants remain queued.
- Icewind Dale: Rime of the Frostmaiden: ten distinctive appendix item names. Cold-weather equipment, special materials, spellbooks, Summer Star and other chapter objects remain queued. The mythallar is an installed-object reference, not backpack equipment.
- Diablo IV: named unique-item snapshot; no current-season certification or D&D class restrictions.
- Conan Exiles Enhanced: public inventory snapshot. Names, categories and IDs only. Building pieces/furnishings/stations have a construction domain; pet tokens are excluded for a future companion registry. Obtainability, DLC and edition differences remain unverified.

Reference indexes contain no source descriptions, game mechanics, official art or copied chapter prose. They require compatibility/conversion work before play. Public-name index coverage does not establish an exhaustive original-book audit.

The resumable fetchers cache HTML outside the distributable and emit whitelisted metadata only:

```sh
/home/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/fetch_next_indexes.py
python3 scripts/seed_backlog_registry.py
python3 scripts/build_catalog.py
```

`research-queue.json` records remaining scopes. Bibliography, chapter leads, ship leads, NPCs and spells do not become additional converted equipment records merely because they were found during research.
