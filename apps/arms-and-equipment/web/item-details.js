"use strict";

function loadSupplement(name) {
    return fetch(name).then(response => response.ok ? response.json() : null).catch(() => null);
}

const itemDetails = Promise.all([
    loadSupplement("bg3-item-rules.json"),
    loadSupplement("curated-item-details.json"),
    loadSupplement("dnd-2024-spell-reference.json"),
    loadSupplement("weapon-profiles-2024.json"),
    loadSupplement("dnd-2024-item-cross-references.json"),
    loadSupplement("legacy-game-weapon-facts.json"),
    loadSupplement("diablo-2-base-weapon-facts.json"),
    loadSupplement("bg3-weapon-availability.json"),
    loadSupplement("core-enhancement-cross-references.json"),
    loadSupplement("diablo-2-unique-weapon-facts.json"),
    loadSupplement("published-2024-weapon-facts.json"),
    loadSupplement("published-2024-armor-facts.json"),
    loadSupplement("bg3-armor-effects.json"),
    loadSupplement("core-armor-cross-references.json"),
    loadSupplement("core-magic-weapon-families.json"),
    loadSupplement("diablo-2-base-armor-facts.json"),
    loadSupplement("diablo-2-unique-armor-facts.json"),
    loadSupplement("srd-2024-source-blocks.json")
]);
const equipmentRulesUrl = "https://www.dndbeyond.com/sources/dnd/br-2024/equipment";
const magicItemRulesUrl = "https://www.dndbeyond.com/sources/dnd/br-2024/magic-items";
const scribing = [[1,15],[1,25],[3,100],[5,150],[10,1000],[25,1500],[40,10000],[50,12500],[60,15000],[120,50000]];
const magicCrafting = {common:[5,50],uncommon:[10,200],rare:[50,2000],"very-rare":[125,20000],legendary:[250,100000]};

function wikiLink(title) {
    return "https://bg3.wiki/wiki/" + title.split("#").map(part => encodeURIComponent(part.replace(/ /g, "_"))).join("#");
}

function appendItemDescription(panel, description) {
    const lines = description.split("\n").map(line => line.replace(/^\s*(?:>\s*)+/, ""));
    const cells = line => line.trim().replace(/^\||\|$/g, "").split("|").map(cell => cell.trim());
    const clean = text => text.replace(/\*{1,3}([^*\n]+)\*{1,3}/g, "$1")
        .replace(/(^|[^\w])_{1,3}([^_\n]+)_{1,3}(?=$|[^\w])/g, "$1$2")
        .replace(/\\([*_])/g, "$1");
    let prose = [];
    const flush = () => {
        if (prose.length) panel.appendChild(element("p", clean(prose.join("\n")), "detail-description"));
        prose = [];
    };
    for (let index = 0; index < lines.length; index++) {
        const line = lines[index].trim();
        if (!line.startsWith("|") || !/^\s*\|[| :\-]+$/.test(lines[index + 1] || "")) {
            prose.push(lines[index]);
            continue;
        }
        flush();
        const table = element("table", "", "item-rule-table");
        const header = table.createTHead().insertRow();
        cells(line).forEach(cell => {
            const heading = element("th", clean(cell));
            heading.scope = "col";
            header.appendChild(heading);
        });
        const body = table.createTBody();
        index++;
        while ((lines[index + 1] || "").trim().startsWith("|")) {
            const row = body.insertRow();
            cells(lines[++index]).forEach(cell => row.appendChild(element("td", clean(cell))));
        }
        const wrapper = element("div", "", "item-rule-table-wrap");
        wrapper.appendChild(table);
        panel.appendChild(wrapper);
    }
    flush();
}

const srdEquipmentPrefix = "open5e-srd-2024:srd-2024_";
const srdLaunchers = {
    "arrows-20": [["shortbow", "Shortbow"], ["longbow", "Longbow"]],
    "bolts-20": [["hand-crossbow", "Hand Crossbow"], ["light-crossbow", "Light Crossbow"], ["heavy-crossbow", "Heavy Crossbow"]],
    "bullets-firearm-10": [["pistol", "Pistol"], ["musket", "Musket"]],
    "bullets-sling-20": [["sling", "Sling"]],
    "needles-50": [["blowgun", "Blowgun"]]
};

function addSrdEquipmentUse(panel, item, returnFocus) {
    if (!item.id.startsWith(srdEquipmentPrefix)) return;
    const slug = item.id.slice(srdEquipmentPrefix.length);
    const launchers = srdLaunchers[slug];
    if (launchers) {
        const use = itemDetailsSection(panel, "Using this ammunition", [
            ["Damage and range", "Use the launcher’s damage and range. Expend one piece per attack."],
            ["Recovery", "After the fight, spend 1 minute to recover half the ammunition you used, rounded down."]
        ], equipmentRulesUrl + "#Ammunition", true);
        launchers.forEach(([id, title]) => {
            const button = element("button", "Open " + title);
            button.addEventListener("click", () => inspect(srdEquipmentPrefix + id, returnFocus));
            use.appendChild(button);
        });
    }
    const mounts = {
        camel: [50, 450], elephant: [40, 1320], "horse-draft": [40, 540],
        "horse-riding": [60, 480], mastiff: [40, 195], mule: [40, 420],
        pony: [40, 225], warhorse: [60, 540]
    };
    if (mounts[slug]) {
        const [speed, capacity] = mounts[slug];
        itemDetailsSection(panel, "Mount statistics", [["Speed", speed + " ft"], ["Carrying capacity", capacity + " lb"]],
            equipmentRulesUrl + "#MountsandVehicles", true);
    }
    const vessels = {
        airship: ["8 mph", 10, 20, 1, 13, 300, "—"],
        galley: ["4 mph", 80, "—", 150, 15, 500, 20],
        keelboat: ["1 mph", 1, 6, "½", 15, 100, 10],
        longship: ["3 mph", 40, 150, 10, 15, 300, 15],
        rowboat: ["1½ mph", 1, 3, "—", 11, 50, "—"],
        "sailing-ship": ["2 mph", 20, 20, 100, 15, 300, 15],
        warship: ["2½ mph", 60, 60, 200, 15, 500, 20]
    };
    if (vessels[slug]) {
        const labels = ["Speed", "Crew", "Passengers", "Cargo (tons)", "AC", "HP", "Damage threshold"];
        itemDetailsSection(panel, "Vessel statistics", labels.map((label, i) => [label, vessels[slug][i]]),
            equipmentRulesUrl + "#MountsandVehicles", true);
    }
    const focusStaff = slug === "druidic-focus-wooden-staff" || slug === "arcane-focus-staff";
    const weaponModes = slug === "rod-of-lordly-might" ? [
        ["mace", "Default · Mace +3"],
        ["longsword", "Button 1 · Longsword with 2d6 extra Fire on hit"],
        ["shortsword", "Button 1 · Shortsword with 2d6 extra Fire on hit"],
        ["battleaxe", "Button 2 · Battleaxe +3"],
        ["spear", "Button 3 · Spear +3"]
    ] : item.type === "staff" && /quarterstaff/i.test(item.description || "")
        ? [["quarterstaff", "Quarterstaff · use the item’s listed magic bonus and effects"]]
        : focusStaff && /quarterstaff/i.test(item.description || "") ? [["quarterstaff", "Open Quarterstaff"]] : [];
    if (weaponModes.length) {
        const details = itemDetailsSection(panel, "Weapon modes", [
            ["Quarterstaff", (item.type === "staff" || focusStaff) ? "1d6 Bludgeoning, 1d8 with two hands. Topple mastery if trained in that mastery." : ""],
            ["Switch modes", slug === "rod-of-lordly-might" ? "Bonus Action. Press the same button again to return to the default form." : ""]
        ], equipmentRulesUrl + "#Weapons", true);
        weaponModes.forEach(([id, label]) => {
            const button = element("button", label);
            button.addEventListener("click", () => inspect(srdEquipmentPrefix + id, returnFocus));
            details.appendChild(button);
        });
    }
    if (slug === "saddle-military") {
        itemDetailsSection(panel, "Military saddle · 2024 equipment rule", [
            ["Benefit", "Advantage on ability checks to remain mounted."],
            ["Falling off", "The DC 10 Dexterity saving throw from forced movement of your mount is a separate roll."]
        ], equipmentRulesUrl + "#Saddles", true);
    }
    const figurines = {
        "bronze-griffon": [["Griffon", "Griffon"]],
        "ebony-fly": [["Giant Fly", "GiantFly"]],
        "golden-lions": [["Lion", "Lion"]],
        "ivory-goats": [["Riding Horse · Goat of Traveling", "RidingHorse"], ["Giant Goat", "GiantGoat"]],
        "marble-elephant": [["Elephant", "Elephant"]],
        "obsidian-stead": [["Nightmare", "Nightmare"]],
        "onyx-dog": [["Mastiff", "Mastiff"]],
        "serpentine-owl": [["Giant Owl", "GiantOwl"]],
        "silver-raven": [["Raven", "Raven"]]
    };
    const figurine = figurines[slug.replace(/^figurine-of-wondrous-power-/, "")];
    if (figurine) {
        const details = itemDetailsSection(panel, "Figurine creature statistics", [],
            magicItemRulesUrl + "-a-z#FigurineofWondrousPower", true);
        figurine.forEach(([label, anchor]) => {
            const url = anchor === "GiantFly" ? magicItemRulesUrl + "-a-z#GiantFly"
                : "https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" + anchor;
            details.appendChild(sourceLink(url, label));
        });
    }
    const summoned = {
        "stone-of-controlling-earth-elementals": ["Earth Elemental", "EarthElemental"],
        "censer-of-controlling-air-elementals": ["Air Elemental", "AirElemental"],
        "brazier-of-commanding-fire-elementals": ["Fire Elemental", "FireElemental"],
        "bowl-of-commanding-water-elementals": ["Water Elemental", "WaterElemental"],
        "horn-of-valhalla": ["Berserker", "Berserker"],
        "pipes-of-the-sewers": ["Swarm of Rats", "SwarmofRats"],
        "staff-of-the-python": ["Giant Constrictor Snake", "GiantConstrictorSnake"]
    };
    const creature = summoned[slug] || (slug.startsWith("horn-of-valhalla-") ? summoned["horn-of-valhalla"] : null);
    if (creature) {
        itemDetailsSection(panel, "Summoned creature", [
            [creature[0], "https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" + creature[1]]
        ], "https://www.dndbeyond.com/srd", true);
    }
    const outcomeCreatures = {
        "elemental-gem": ["Air Elemental", "Earth Elemental", "Fire Elemental", "Water Elemental"],
        "wand-of-wonder": ["Rhinoceros", "Elephant", "Rat", "Black Bear", "Giant Wasp", "Frog"]
    }[slug];
    if (outcomeCreatures) {
        const details = itemDetailsSection(panel, "Creature outcomes", [], "", true);
        for (const name of outcomeCreatures) {
            details.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" +
                name.replace(/ /g, ""), name));
        }
    }
    if (slug === "bag-of-tricks") {
        const creaturesByBag = {
            Gray: ["Weasel", "Giant Rat", "Badger", "Boar", "Panther", "Giant Badger", "Dire Wolf", "Giant Elk"],
            Rust: ["Rat", "Owl", "Mastiff", "Goat", "Giant Goat", "Giant Boar", "Lion", "Brown Bear"],
            Tan: ["Jackal", "Ape", "Baboon", "Axe Beak", "Black Bear", "Giant Weasel", "Giant Hyena", "Tiger"]
        };
        for (const [color, creatures] of Object.entries(creaturesByBag)) {
            const details = itemDetailsSection(panel, color + " bag · creature statistics", []);
            creatures.forEach((name, index) => details.appendChild(sourceLink(
                "https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" + name.replace(/ /g, ""),
                (index + 1) + " · " + name)));
        }
    }
    if (slug === "feather-token-bird" || slug === "mysterious-deck") {
        const [creatureName, anchor] = slug === "mysterious-deck" ? ["Knight", "Knight"] : ["Roc", "Roc"];
        const details = itemDetailsSection(panel, "Referenced creature statistics", [], "", true);
        details.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" + anchor,
            creatureName));
    }
    if (["feather-token-anchor", "feather-token-fan", "feather-token-swan-boat"].includes(slug)) {
        panel.appendChild(sourceLink(equipmentRulesUrl + "#MountsandVehicles", "Vessel rules"));
    }
    if (item.mechanics && item.mechanics.variant_rarities) {
        itemDetailsSection(panel, "Rarity by horn material", Object.entries(item.mechanics.variant_rarities),
            magicItemRulesUrl + "-a-z#HornofValhalla", true);
    }
    if (slug === "robe-of-useful-items") {
        const details = itemDetailsSection(panel, "Creatures from patches", [], "", true);
        for (const [label, anchor] of [["Riding Horse", "RidingHorse"], ["Mastiff", "Mastiff"]]) {
            details.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" + anchor, label));
        }
    }
    if (slug === "manual-of-golems") {
        const details = itemDetailsSection(panel, "Golem statistics", [], "", true);
        for (const material of ["Clay", "Flesh", "Iron", "Stone"]) {
            details.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" +
                material + "Golem", material + " Golem"));
        }
    }
    if (slug === "bag-of-beans") {
        const details = itemDetailsSection(panel, "Creatures from planted beans", [], "", true);
        for (const [label, anchor] of [["Treant", "Treant"], ["Shrieker Fungus", "ShriekerFungus"],
            ["Bulette", "Bulette"], ["Mummy", "Mummy"], ["Mummy Lord", "MummyLord"]]) {
            details.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks#" + anchor, label));
        }
    }
    const giantBaneItems = slug.startsWith("hammer-of-thunderbolts-") ? [
        ["gauntlets-of-ogre-power", "Gauntlets of Ogre Power"],
        ...[["hill", "Hill"], ["frost-or-stone", "Frost or Stone"], ["fire", "Fire"], ["cloud", "Cloud"],
            ["storm", "Storm"]].map(([id, label]) => ["belt-of-giant-strength-" + id, "Belt of Giant Strength · " + label])
    ] : null;
    const companionItems = giantBaneItems || {
        "talisman-of-the-sphere": [["sphere-of-annihilation", "Sphere of Annihilation · baseline control rules"]],
        "sovereign-glue": [["universal-solvent", "Universal Solvent"], ["oil-of-etherealness", "Oil of Etherealness"],
            ["oil-of-slipperiness", "Oil of Slipperiness · storage"]],
        "universal-solvent": [["sovereign-glue", "Sovereign Glue"]],
        "folding-boat": [["rowboat", "Rowboat"], ["keelboat", "Keelboat"]],
        "robe-of-useful-items": [["rowboat", "Rowboat"], ["ram-portable", "Portable Ram"]]
    }[slug];
    if (companionItems) {
        const details = itemDetailsSection(panel, "Related items", [], "", true);
        companionItems.forEach(([id, label]) => {
            const button = element("button", label);
            button.addEventListener("click", () => inspect(srdEquipmentPrefix + id, returnFocus));
            details.appendChild(button);
        });
    }
    const warMage = /^wand-of-the-war-mage-plus-([123])$/.exec(slug);
    if (warMage) {
        itemDetailsSection(panel, "Wand of the War Mage", [
            ["Spell attack bonus", "+" + warMage[1]], ["Cover", "Ignore Half Cover on spell attacks."]
        ], magicItemRulesUrl + "-a-z#WandoftheWarMage1or2or3", true);
    }
    if (slug === "necklace-of-fireballs") {
        itemDetailsSection(panel, "Detonate the beads", [
            ["Activation", "Magic action to detach and throw one or more beads up to 60 ft."],
            ["Area", "20 ft radius Sphere centered where the beads land."],
            ["Save and damage", "DC 15 Dexterity. 8d6 Fire for one bead, +1d6 per extra bead (maximum 12d6). Half on a success."]
        ], magicItemRulesUrl + "-a-z#NecklaceofFireballs", true);
    }
    if (slug === "wand-of-fireballs") {
        itemDetailsSection(panel, "Cast Fireball from the wand", [
            ["Activation", "Magic action while holding the wand. Spend 1–3 of its 7 charges for spell level 3–5."],
            ["Target", "Point within 150 ft. The blast fills a 20 ft radius."],
            ["Save and damage", "DC 15 Dexterity. 8d6 Fire at level 3, +1d6 per additional charge. Half on a success."],
            ["Recovery", "Regain 1d6 + 1 spent charges at dawn. After spending the last charge, a 1 on 1d20 destroys the wand."]
        ], magicItemRulesUrl + "-a-z#WandofFireballs", true);
    }
}

function itemDetailsSection(panel, label, rows, url, open) {
    const details = element("details", "", "weapon-feature");
    details.open = !!open;
    details.appendChild(element("summary", label));
    statList(details, rows);
    if (url) details.appendChild(sourceLink(url, "Open source"));
    panel.appendChild(details);
    return details;
}

function addBg3ItemDetails(panel, itemId, record, effects, armorRules) {
    const reviewed = (armorRules.reviewed_item_facts || {})[itemId] || {};
    if (reviewed.Activation && reviewed.Duration && reviewed["Special powers"]) {
        panel.appendChild(element("p", feetText(reviewed["Special powers"][0]), "rule verified-bg3-summary"));
    }
    record.variants.forEach((variant, index) => {
        const stats = variant.stats;
        const facts = {...variant.facts, ...reviewed};
        const armorEffects = armorRules.effects || {};
        const shieldTraining = stats.type === "Shields" && !stats.proficiency && armorRules.shield_training;
        const exemption = variant.effects.map(title => armorEffects[title])
            .find(effect => effect && effect.facts.Training);
        const rows = [
            ["Activation", pretty(stats["usage cost"])],
            ["Single use", pretty(stats["single use"])],
            ["Armor class", stats["armour class"]],
            ["Armor class bonus", stats["armour class bonus"]],
            ["Armor type", stats["armour type"]],
            ["Training", exemption ? exemption.facts.Training.join(" · ") : stats.proficiency || (shieldTraining && shieldTraining.label)],
            ["Stealth disadvantage", pretty(stats["stealth disadvantage"])],
            ["Enchantment", stats.enchantment],
            ["Camp supplies", stats["camp supplies"]],
            ["Weight", stats["weight kg"] ? stats["weight kg"] + " kg" : ""],
            ["Object hit points", stats.hp],
            ["Surface", stats.area],
            ["Surface size", [distanceInFeet(stats["area range ft"], stats["area range m"]),
                stats["area shape"]].filter(Boolean).join(" · ")],
            ["Surface duration", /^\d+$/.test(stats["area duration"] || "")
                ? stats["area duration"] + " turns" : stats["area duration"]],
            ["Author", stats["book author"]]
        ];
        Object.keys(facts).forEach(key => rows.push([key, facts[key].join(" · ")]));
        rows.push(...effectStatRows(variant.conditions));
        if (variant.locations.length) rows.push(["Where to find", variant.locations.join(" · ")]);
        if (variant.acquisition_refs.length) rows.push(["Acquisition references", variant.acquisition_refs.join(" · ")]);
        if (variant.recipe_refs.length) rows.push(["Crafting references", variant.recipe_refs.join(" · ")]);
        if (!rows.some(row => row[1]) && !variant.effects.length && !variant.has_rule_text) return;
        const label = record.variants.length > 1 ? "BG3 item details · " + (stats.name || "Variant " + (index + 1)) : "BG3 item details";
        const source = "https://bg3.wiki/w/index.php?oldid=" + record.revision;
        const details = itemDetailsSection(panel, label, rows, source, true);
        if (shieldTraining) details.appendChild(sourceLink(
            "https://bg3.wiki/w/index.php?oldid=" + shieldTraining.revision, "BG3 shield training"));
        variant.effects.forEach(title => {
            const effect = armorEffects[title] || effects[title];
            if (!effect) {
                details.appendChild(sourceLink(wikiLink(title), title));
                return;
            }
            const facts = Object.entries(effect.facts).map(([key, values]) => [key, values.join(" · ")]);
            const stats = effectStatRows(effect.stats);
            itemDetailsSection(details, effect.title, stats.concat(facts),
                "https://bg3.wiki/w/index.php?oldid=" + effect.revision);
        });
        if (variant.has_rule_text && !Object.keys(facts).length && !variant.effects.length) {
            details.appendChild(element("p", "The source describes an effect that has not been entered as structured rules.", "meta"));
        }
    });
}

function spellReference(panel, spell, source, originalEdition, item, option = {}) {
    const {fixedLevel, qualifier, charges, component, outcome, bead} = option;
    const scalingDamage = fixedLevel && ["Fireball", "Lightning Bolt"].includes(spell.name)
        ? (8 + fixedLevel - 3) + "d6" : "";
    const spellText = spell.desc || "";
    const saveAbility = pretty(spell.saving_throw_ability);
    const sourceHasSave = saveAbility && spellText.toLowerCase().includes(saveAbility.toLowerCase() + " saving throw");
    const sourceHasDamage = spell.damage_roll && spellText.includes(spell.damage_roll) &&
        /\bdamage\b/i.test(spellText) && !["Wish", "Web", "Gaseous Form", "Ray of Enfeeblement", "Bless", "Dimension Door"].includes(spell.name);
    const damageType = spell.name === "Conjure Elemental" ? "of the spirit’s type, then 4d8 on repeat failed saves"
        : (spell.damage_types || []).map(pretty).join(", ");
    const wandScaling = {
        "wand-of-magic-missiles": ["Magic Missile", "1–3 charges cast at levels 1–3, creating 3–5 darts."],
        "wand-of-lightning-bolts": ["Lightning Bolt", "1–3 charges cast at levels 3–5, dealing 8d6–10d6 Lightning."],
        "wand-of-fireballs": ["Fireball", "1–3 charges cast at levels 3–5, dealing 8d6–10d6 Fire."]
    }[item.id.slice(srdEquipmentPrefix.length)];
    const blasting = item.id === srdEquipmentPrefix + "circlet-of-blasting" && spell.name === "Scorching Ray";
    const coneOverride = qualifier && /^(\d+)-foot cone$/i.exec(qualifier);
    const area = spell.name === "Lightning Bolt" ? "100 ft long × 5 ft wide Line"
        : spell.shape_type && spellText.toLowerCase().includes(spell.shape_type.toLowerCase())
            ? [pretty(spell.shape_type), spell.shape_size, spell.shape_size_unit].filter(Boolean).join(" ") : "";
    const cloakWeb = item.id === srdEquipmentPrefix + "cloak-of-arachnida" && spell.name === "Web";
    const batCloak = item.id === srdEquipmentPrefix + "cloak-of-the-bat" && spell.name === "Polymorph";
    const selfLevitate = spell.name === "Levitate" && /cast Levitate on yourself/i.test(item.description || "");
    const selfOnly = selfLevitate || batCloak || item.id.startsWith(srdEquipmentPrefix) &&
        /(?:can target only yourself|targeting only yourself|target only yourself)/i.test(item.description || "");
    const description = item.description || "";
    const potionEffect = item.type === "potion" && /\b(?:gain|are under) the (?:["“](?:reduce|enlarge)["”] )?effect of the/i.test(description);
    const potionDuration = potionEffect && /(?:for|last for) (\d+(?:d\d+)? (?:minutes?|hours?))/i.exec(description);
    const sensorSuggestion = item.id === srdEquipmentPrefix + "crystal-ball-of-telepathy" && spell.name === "Suggestion";
    const noConcentration = sensorSuggestion || (potionEffect && /no Concentration required/i.test(description)) ||
        (item.id === srdEquipmentPrefix + "crystal-ball-of-mind-reading" && spell.name === "Detect Thoughts");
    const potionRestriction = {
        "potion-of-diminution": "Reduce only.",
        "potion-of-growth": "Enlarge only.",
        "potion-of-speed": "The effect ends without the spell’s wave of lethargy."
    }[item.id.slice(srdEquipmentPrefix.length)];
    const potionArea = potionEffect && spell.name === "Clairvoyance";
    const oilEffect = /oil-of-(etherealness|slipperiness)$/.test(item.id);
    const oilGround = oilEffect && spell.name === "Grease";
    const oilDuration = oilEffect ? (spell.name === "Etherealness" ? "1 hour" : "8 hours") : "";
    const itemSave = outcome ? [null, "15"] : /save DC (\d+)/i.exec(item.description || "");
    const gaseous = spell.name === "Gaseous Form";
    const animalFear = item.id === srdEquipmentPrefix + "ring-of-animal-influence" && spell.name === "Fear";
    const details = itemDetailsSection(panel, "2024 spell reference · " + spell.name, [
        ["Spell level", fixedLevel || (spell.level === 0 ? "Cantrip" : spell.level)],
        ["Casting time", bead ? "Bonus Action while wearing the necklace" : oilGround ? "Magic action to pour the oil" : oilEffect ? "10 minutes to apply the oil" : potionEffect ? "Effect begins when you drink it" : pretty(spell.casting_time).replace(/(\d)([a-z])/gi, "$1 $2")],
        ["Casting trigger", spell.casting_trigger],
        ["Reaction trigger", spell.reaction_condition],
        ["Range", outcome ? "Use the wand’s selected point and the outcome’s targeting rule" : sensorSuggestion ? "Target through the Scrying sensor" : oilGround ? "10 ft square coated by the oil" : oilEffect ? "Coated creature" : selfOnly || (potionEffect && !potionArea) ? "Self (item restriction)" : spell.range_text],
        ["Area", outcome && ["Gust of Wind", "Lightning Bolt"].includes(spell.name) ? "Line from you to the chosen point" : cloakWeb ? "Twice the base spell’s area" : coneOverride ? coneOverride[1] + " ft Cone" : oilGround ? "10 ft square" : area],
        ["Charge cost", charges === 0 ? "0 charges" : charges],
        ["Gem consumed", component],
        ["Bead", bead],
        ["Recovery", bead ? "That bead can be used again at the next dawn." : ""],
        ["Rolled outcome", outcome],
        ["Charge scaling", wandScaling && wandScaling[0] === spell.name ? wandScaling[1] : ""],
        ["Spell option restriction", qualifier && !fixedLevel && !coneOverride ? qualifier : ""],
        ["Duration", outcome && spell.name === "Enlarge/Reduce" ? "See the rolled outcome (self-reduction lasts 1 minute)" : sensorSuggestion ? "Ends when Scrying ends" : oilDuration || (potionDuration ? potionDuration[1] : spell.duration)],
        ["Concentration", noConcentration
            ? "None for this item’s effect" : spell.concentration ? "Required" : ""],
        ["Healing", spell.name === "Cure Wounds" && fixedLevel ? (fixedLevel * 2) + "d8 + spellcasting ability modifier" : ""],
        ["Damage", spell.name === "Prismatic Spray" ? "12d6 on rays 1–5 (half on a successful save). See the ray table for types and other effects." : sourceHasDamage ? [scalingDamage || spell.damage_roll, damageType,
            spell.name === "Magic Missile" ? "per dart" : spell.name === "Scorching Ray" ? "per ray" : ""].filter(Boolean).join(" ") : ""],
        ["Saving throw", selfLevitate || gaseous || spell.name === "Haste" || (potionEffect && spell.name === "Enlarge/Reduce") ? "" :
            batCloak ? "None for this self-targeted use" : cloakWeb ? "DC 13 Dexterity" :
            sourceHasSave ? (itemSave ? "DC " + itemSave[1] + " " : bead ? "Your spell save DC · " : "") + saveAbility : ""],
        ["Darts", fixedLevel && spell.name === "Magic Missile" ? fixedLevel + 2 : ""],
        ["Spell attack", blasting ? "+5 to hit for each of three rays" : ""],
        ["Targets", fixedLevel && spell.name === "Animal Friendship" ? "Up to " + fixedLevel + " Beasts"
            : spell.name === "Animal Messenger" && item.id.endsWith("figurine-of-wondrous-power-silver-raven") ? "The figurine in Raven form" : ""],
        ["Blocked arrival", spell.name === "Dimension Door" ? "If the destination is occupied or lacks room, each teleporter takes 4d6 Force damage and the teleport fails." : ""],
        ["End early", gaseous && potionDuration ? "Use a Bonus Action to end the potion’s effect." : ""],
        ["Item restrictions", potionRestriction || (animalFear ? "Affects Beasts only." : batCloak ? "Dim Light or Darkness. Become a Bat and retain Intelligence, Wisdom, and Charisma. Usable again at dawn." : "")]
    ], source, true);
    if (fixedLevel || qualifier || bead || outcome || sensorSuggestion || cloakWeb || selfOnly || potionEffect || oilEffect ||
        (item.id === srdEquipmentPrefix + "crystal-ball-of-mind-reading" && spell.name === "Detect Thoughts")) {
        details.appendChild(element("h4", "Base spell text"));
    }
    appendItemDescription(details, feetText(spell.desc));
    if (spell.higher_level) {
        details.appendChild(element("h4", "Using a Higher-Level Spell Slot · spell reference"));
        if (item.type !== "scroll") {
            details.appendChild(element("p",
                "Use the level and targets granted by this item. Higher-level spell text applies only when the item explicitly grants that level.",
                "meta"));
        }
        appendItemDescription(details, spell.higher_level);
    }
    if (spell.name === "Giant Insect") {
        details.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/spell-descriptions#GiantInsect",
            "Giant Insect spell and stat block"));
    }
    if (originalEdition !== "dnd-2024") {
        details.appendChild(element("p", "The original item uses its source edition.", "meta"));
    }
}

function addSpellReference(panel, item, spells) {
    if (!spells) return;
    const reference = (item.mechanics || {}).reference_metadata || {};
    const inscribed = reference.inscribed_spell || {};
    const byName = item.ruleset === "dnd-2024" && item.type === "scroll"
        ? /^Spell Scroll\s*\(([^)]+)\)$/i.exec(item.name) : null;
    const name = inscribed.name || (byName && byName[1]);
    if (!name) {
        if (item.ruleset !== "dnd-2024" || !item.description) return;
        const text = item.description.toLowerCase().replace(/[*_]/g, "");
        const names = Object.keys(spells.spells).sort((a,b) => b.length - a.length);
        const matches = new Set();
        const casting = /\b(?:cast\s+(?:the\s+)?(?:level (\d+) version of (?:the\s+)?)?|(?:gains?|are under|duplicating) the (?:["“](?:reduce|enlarge)["”] )?effect of the\s+)/g;
        const options = new Map();
        let match;
        while ((match = casting.exec(text))) {
            const tail = text.slice(casting.lastIndex);
            const found = names.find(candidate => tail.startsWith(candidate) && !/[a-z]/.test(tail[candidate.length] || ""));
            if (found) {
                matches.add(found);
                if (match[1]) options.set(found, {fixedLevel: Number(match[1])});
                const alternative = /^\s+or\s+/.exec(tail.slice(found.length));
                if (alternative) {
                    const remainder = tail.slice(found.length + alternative[0].length);
                    const second = names.find(candidate => remainder.startsWith(candidate) &&
                        !/[a-z]/.test(remainder[candidate.length] || ""));
                    if (second) matches.add(second);
                }
            }
        }
        if (item.id === srdEquipmentPrefix + "ring-of-animal-influence") {
            ["animal friendship", "fear", "speak with animals"].filter(key => spells.spells[key]).forEach(key => matches.add(key));
        }
        if (item.id === srdEquipmentPrefix + "sovereign-glue" && spells.spells.wish) {
            matches.add("wish");
        }
        const dashSpells = /cast the following spells from it:\s*((?:- [^-]+)+?)(?= Protective Aura\.)/i.exec(item.description);
        if (dashSpells) {
            for (const entry of dashSpells[1].split(/-\s+/)) {
                const key = entry.trim().toLowerCase();
                if (spells.spells[key]) matches.add(key);
            }
        }
        if (item.id === srdEquipmentPrefix + "staff-of-charming") {
            for (const key of ["charm person", "command", "comprehend languages"]) {
                if (spells.spells[key]) {
                    matches.add(key);
                    options.set(key, {charges: 1});
                }
            }
        }
        if (item.id === srdEquipmentPrefix + "wand-of-wonder") {
            const outcomes = {
                darkness: "01–20, then 1–2 on 1d10. Origin is the chosen point.",
                "faerie fire": "01–20, then 3–4 on 1d10. Origin is the chosen point.",
                fireball: "01–20, then 5–6 on 1d10. Origin is the chosen point.",
                slow: "01–20, then 7–8 on 1d10. Origin is the chosen point.",
                "stinking cloud": "01–20, then 9–10 on 1d10. Origin is the chosen point.",
                "gust of wind": "26–30. Line extends from you to the chosen point.",
                "lightning bolt": "46–50. Line extends from you to the chosen point.",
                "enlarge/reduce": "51–55 enlarges the closest creature, or you if it is ineligible. 69–72 reduces you for 1 minute.",
                invisibility: "83–87. You are the target.",
                polymorph: "93–97. Closest creature becomes a Black Bear, Giant Wasp, or Frog according to the roll."
            };
            for (const [key, outcome] of Object.entries(outcomes)) {
                if (spells.spells[key]) {
                    matches.add(key);
                    options.set(key, {outcome});
                }
            }
        }
        if (item.id === srdEquipmentPrefix + "necklace-of-prayer-beads") {
            for (const line of item.description.split("\n")) {
                const row = /^\s*\|[^|]+\|\s*(Bead of [^|]+?)\s*\|\s*([^|]+?)\s*\|/i.exec(line);
                if (!row) continue;
                const qualified = /^(.*?) \(level (\d+) version\)$/.exec(row[2]);
                const key = (qualified ? qualified[1] : row[2]).toLowerCase();
                if (!spells.spells[key]) continue;
                matches.add(key);
                options.set(key, {bead: row[1], fixedLevel: qualified ? Number(qualified[2]) : null});
            }
        }
        const gemSpells = /using one of the helm's gems[^:]+:\s*([^.]*)/i.exec(item.description);
        if (gemSpells) {
            for (const match of gemSpells[1].matchAll(/([a-z][a-z ]*?)\s+\(([^)]+)\)/gi)) {
                const key = match[1].trim().replace(/^or /i, "").toLowerCase();
                if (!spells.spells[key]) continue;
                matches.add(key);
                options.set(key, {component: match[2]});
            }
        }
        if (/\|\s*Spell\s*\|\s*Charge Cost/i.test(item.description)) {
            for (const line of item.description.replace(/[*_]/g, "").split("\n")) {
                const match = /^\s*\|\s*([^|]+?)\s*\|\s*(\d[^|]*?)\s*\|/.exec(line);
                if (!match) continue;
                const qualified = /^(.*?) \((.+)\)$/.exec(match[1]);
                const key = (qualified ? qualified[1] : match[1]).toLowerCase();
                const qualifier = qualified && qualified[2];
                const level = qualifier && /^level (\d+) version$/i.exec(qualifier);
                if (!spells.spells[key]) continue;
                matches.add(key);
                options.set(key, {qualifier, fixedLevel: level ? Number(level[1]) : null, charges: /^\d+$/.test(match[2]) ? Number(match[2]) : match[2]});
            }
        }
        matches.forEach(found => spellReference(panel, spells.spells[found], spells.srd, item.ruleset, item,
            options.get(found)));
        return;
    }
    const spell = spells.spells[name.toLowerCase()];
    const level = spell ? spell.level : inscribed.level;
    const timeCost = Number.isInteger(level) && scribing[level];
    if (spell) {
        spellReference(panel, spell, spells.srd, item.ruleset, item);
    }
    if (timeCost) {
        itemDetailsSection(panel, "Scribing a 2024 scroll", [
            ["Time", timeCost[0] + (timeCost[0] === 1 ? " day" : " days")],
            ["Cost", timeCost[1].toLocaleString() + " gp"],
            ["Requirements", "Arcana or Calligrapher’s Supplies proficiency. Prepare the spell on each workday and supply its material components."],
            ["Spell materials", spell && spell.material_specified]
        ], equipmentRulesUrl + "#ScribingSpellScrolls");
    }
}

function addPublishedEquipment(panel, item, published, core) {
    const counterpart = core && core.records[item.id];
    const family = core && core.modern && core.modern[item.id];
    const armorRule = counterpart || family;
    const reference = published && published.records[item.id];
    const base = counterpart ? JSON.parse(Armory.item(counterpart.target_id))
        : reference ? JSON.parse(Armory.item(reference.base_id)) : item;
    const mechanics = base.mechanics || {};
    const attunement = (counterpart ? base : item).requires_attunement;
    const armor = mechanics.armor;
    if (!armor || !Number.isInteger(armor.ac_base)) return;
    const shield = armor.name === "Shield";
    const enhancement = item.source_id === "open5e-srd-2024" &&
        /bonus to Armor Class/i.test(item.description || "") && item.name.match(/ \(\+([123])\)$/);
    const bonus = armorRule ? armorRule.bonus || 0 : reference ? reference.bonus : enhancement ? Number(enhancement[1]) : 0;
    let ac = shield ? "+" + (armor.ac_base + bonus) : armor.ac_base + bonus;
    if (armor.ac_add_dexmod) {
        ac += " + Dex modifier" + (armor.ac_cap_dexmod == null ? "" : " (max +" + armor.ac_cap_dexmod + ")");
    }
    itemDetailsSection(panel, counterpart ? "Verified 2024 armor counterpart" : "Armor statistics", [
        ["Base armor", armor.name],
        [shield ? "Armor class bonus" : "Armor class", ac],
        ["Training", (armorRule && armorRule.training) || ((armor.document === "srd-2024" || armor.document === "srd-2014")
            ? (shield ? "Shield" : armor.ac_add_dexmod
                ? (armor.ac_cap_dexmod == null ? "Light armor" : "Medium armor") : "Heavy armor") : "")],
        ["Strength requirement", armorRule && armorRule.mithral ? "None" : armor.strength_score_required || ""],
        ["Stealth disadvantage", armorRule && armorRule.mithral ? "No" : armor.grants_stealth_disadvantage ? "Yes" : ""],
        ["Weight", Number((mechanics.source_fields || {}).weight) > 0 ? Number(mechanics.source_fields.weight) + " lb" : ""],
        ["Attunement", attunement === true ? "Required" : attunement === false ? "None" : ""],
        ["Special powers", armorRule ? armorRule.effect : reference && reference.effects],
        ["2024 rules note", counterpart && counterpart.change]
    ], armorRule ? armorRule.source : reference ? published.source : item.ruleset === "dnd-2024" ? equipmentRulesUrl : "", true);
}

function addRecordedEncounters(panel, item) {
    const reference = (item.mechanics || {}).reference_metadata || {};
    const proof = item.provenance || {};
    const research = item.research_metadata || {};
    const entries = [reference].concat(reference.attested_appearances || [],
        proof.additional_sources || [], research.source_refs || []);
    const seen = new Set();
    const encounters = [];
    entries.forEach((entry, index) => {
        const locator = entry.locator || {};
        const location = locator.area || locator.room || locator.encounter || locator.location;
        if (typeof location !== "string") return;
        const label = [locator.chapter && "Chapter " + locator.chapter,
            locator.printed_page && "p. " + locator.printed_page, location].filter(Boolean).join(" · ");
        if (seen.has(label)) return;
        seen.add(label);
        encounters.push({label, note:entry.note || entry.source_note, url:entry.url});
    });
    if (!encounters.length) return;
    const details = itemDetailsSection(panel, "Recorded encounters and locations", []);
    encounters.forEach(entry => {
        const row = element("p", "", "meta");
        row.appendChild(sourceLink(entry.url, entry.label));
        if (entry.note) row.appendChild(document.createTextNode(" · " + entry.note));
        details.appendChild(row);
    });
}

function add2024Crafting(panel, item) {
    if (item.ruleset !== "dnd-2024" || item.source_id !== "open5e-srd-2024") return;
    if (item.id === "open5e-srd-2024:srd-2024_potion-of-healing") {
        itemDetailsSection(panel, "Brewing · 2024 rules", [
            ["Time", "1 day (8 hours)"], ["Materials", "25 gp"], ["Requirements", "Herbalism Kit and proficiency with it"]
        ], equipmentRulesUrl + "#BrewingPotionsofHealing");
        return;
    }
    if (["mount", "waterborne-vehicle", "airborne-vehicle", "flying-vehicle"].includes(item.type)) return;
    const price = ((item.valuation || {}).base_values || []).find(value => value.economy_id === "dnd-2024");
    if (item.magic === false && price && Number(price.amount_gp) > 0) {
        const gp = Number(price.amount_gp);
        const rows = [["Time", Math.ceil(gp / 10) + (gp <= 10 ? " day" : " days")]];
        rows.push(["Materials", gp >= 2 ? Math.floor(gp / 2) + " gp" : "Half the list price, rounded down under the crafting rule"]);
        rows.push(["Requirements", "Proficiency with the appropriate tools. The DM determines material availability."]);
        itemDetailsSection(panel, "Crafting · 2024 nonmagical guideline", rows, equipmentRulesUrl + "#CraftingNonmagicalItems");
    } else if (item.magic === true && magicCrafting[item.rarity] && item.type !== "scroll") {
        const category = String(item.category || "").toLowerCase();
        if (category.indexOf("scroll") >= 0 || item.name.toLowerCase().indexOf("scroll") >= 0) return;
        const singleUse = item.type === "potion" || /^(ammunition|arrow)\b/i.test(item.name);
        const divisor = singleUse ? 2 : 1;
        const [days, gp] = magicCrafting[item.rarity];
        itemDetailsSection(panel, "Crafting · 2024 rarity guideline", [
            ["Base work", (days / divisor).toLocaleString() + " days at 8 hours per day"],
            ["Base materials", (gp / divisor).toLocaleString() + " gp"],
            ["Requirements", "Arcana and the appropriate tool proficiency. Add the base item's cost when required. Prepare any spells the item casts."]
        ], magicItemRulesUrl + "#CraftingMagicItems");
    }
}

function addWeaponProfile(panel, item, supplement) {
    const profile = supplement && supplement.records[item.id];
    if (!profile) return;
    if (profile.base_id) {
        addTabletopWeapon(panel, item, profile);
        panel.appendChild(element("p", profile.basis, "meta"));
        (profile.notes || []).forEach(note => panel.appendChild(element("p", note, "meta")));
        if (profile.source) panel.appendChild(sourceLink(profile.source, "Original item source"));
        if (profile.related_source) panel.appendChild(sourceLink(profile.related_source, "Fan conversion"));
        panel.appendChild(sourceLink(supplement.rules, "2024 base weapon rules"));
    } else if (profile.kind === "improvised-2024") {
        const details = itemDetailsSection(panel, "2024 provisional profile · DM review", [
            ["Damage", "1d4 · type chosen by the DM"],
            ["Range if thrown", "20/60 ft"],
            ["Proficiency", "Improvised weapon rules"]
        ], supplement.improvised_rules, true);
        details.appendChild(element("p", profile.basis, "meta"));
    } else if (["launcher", "reference-object", "weapon-upgrade"].includes(profile.kind)) {
        panel.appendChild(element("p", profile.basis, "meta"));
    }
}

function addPublishedCrossReference(panel, item, references, enhancements) {
    const match = enhancements && enhancements.records[item.id];
    const ordinary = enhancements && enhancements.plain && enhancements.plain[item.id];
    const id = match ? match.target_id : ordinary ? ordinary.target_id : references && references.records[item.id];
    if (!id) return false;
    const published = JSON.parse(Armory.item(id));
    if (!published.description) return false;
    const source = ((published.provenance || {}).source_url || "https://www.dndbeyond.com/srd");
    const verified = match && match.target_id === id;
    const label = verified ? "Verified 2024 enhancement" : ordinary ? "Verified 2024 equipment counterpart" : "Published 2024 cross-reference";
    const basis = verified ? (match.base_note ? "Published 2024 enhancement and base weapon"
        : "Same enhancement and base weapon in the 2014 and 2024 SRDs")
        : ordinary ? "Published 2024 equipment rules" : "Same name and item type in the 2024 SRD";
    const details = itemDetailsSection(panel, label + " · " + published.name,
        [["Match", basis], ["2024 rules note", verified ? match.base_note : ordinary && ordinary.base_note]],
        verified ? enhancements.source : ordinary ? equipmentRulesUrl + (ordinary.role === "adventuring-gear" ? "#Net" : "#Weapons") : source,
        verified || !!ordinary || !item.description);
    if ((verified && match.base_note) || (ordinary && ordinary.base_note)) {
        details.appendChild(sourceLink(equipmentRulesUrl + "#Weapons", "2024 weapon table"));
        if (published.name === "Sling" || published.name.startsWith("Sling ")) details.appendChild(sourceLink(
            "https://www.dndbeyond.com/sources/dnd/basic-rules-2014/equipment#Weapons", "2014 weapon table"));
    }
    details.appendChild(element("p", feetText(published.description), "detail-description"));
    if (published.type === "weapon") {
        const profile = verified ? {kind: "source-based-2024", base_id: match.base_id, bonus: match.bonus} : undefined;
        addTabletopWeapon(details, published, profile);
    }
    return true;
}

function addLegacyDmgDetails(panel, item) {
    if (!["dmg-1e-reference", "dmg-2e-reference"].includes(item.source_id)) return;
    const reference = (item.mechanics || {}).reference_metadata || {};
    const locator = reference.locator || {};
    const fields = {
        source_xp_award: "Experience award", source_sale_gp: "Sale value (gp)",
        source_base_value_gp: "Base value (gp)", source_hit_point_range: "Hit points",
        source_attack_modes: "Attack modes", source_delivery: "Delivery", source_onset: "Onset",
        source_strength: "Poison strength", source_ac_adjustment: "AC adjustment",
        source_weight_adjustment: "Weight adjustment", source_cost_multiplier: "Cost multiplier",
        legacy_armor_class: "Armor class", legacy_ac_bonus: "AC bonus",
        legacy_save_bonus: "Save bonus", legacy_save_radius_ft: "Save radius (ft)",
        source_strength_score: "Strength score", source_weight_lb: "Weight (lb)",
        source_capacity_lb: "Capacity (lb)", source_capacity_cu_ft: "Capacity (cu ft)",
        source_class_qualifier: "Class qualifier"
    };
    const rows = [["Table", locator.table], ["Roll", locator.roll]];
    Object.entries(fields).forEach(([key, label]) => {
        const value = reference[key];
        if (value !== undefined && value !== null) {
            rows.push([label, Array.isArray(value) ? value.join(" / ") : String(value)]);
        }
    });
    const source = locator.description_url || (item.provenance || {}).source_url;
    const details = itemDetailsSection(panel, (reference.reported_edition || "AD&D") + " source data", rows, source);
    for (const configuration of reference.source_configurations || []) {
        const facts = Object.entries(configuration).filter(([key]) => key !== "source_url")
            .map(([key, value]) => [pretty(key), String(value)]);
        itemDetailsSection(details, "Source variant" + (configuration.roll ? " · " + configuration.roll : ""),
            facts, configuration.source_url);
    }
}

function addItemDetails(panel, item, supplements, returnFocus) {
    const [bg3, curated, spells, weapons, references, legacyGames, diabloWeapons, bg3Availability, enhancements,
        diabloUniques, publishedFacts, publishedArmor, bg3Armor, coreArmor, magicFamilies, diabloArmor,
        diabloUniqueArmor, sourceBlocks] = supplements;
    const sourceBlock = sourceBlocks && sourceBlocks.records[item.id];
    if (sourceBlock) {
        const details = itemDetailsSection(panel, sourceBlock.label, [], "", true);
        appendItemDescription(details, sourceBlock.text);
        details.appendChild(sourceLink(sourceBlock.url, "Official SRD · pages " + sourceBlock.pages));
        const copy = element("button", "Copy source text");
        copy.addEventListener("click", () => Armory.copyEntry(item.name, sourceBlock.text));
        details.appendChild(copy);
        statList(details, [["Source text MD5", sourceBlock.md5]]);
    }
    const legacyGame = (legacyGames && legacyGames.records[item.id]) ||
        (diabloWeapons && diabloWeapons.records[item.id]) ||
        (diabloUniques && diabloUniques.records[item.id]);
    const availability = bg3Availability && bg3Availability.records[item.id];
    if (availability) {
        itemDetailsSection(panel, "BG3 availability", [["Player access", availability.note]], availability.source, true);
    }
    if (legacyGame) {
        legacyGame.variants.forEach((variant, index) => {
            const label = legacyGame.game + " · Game statistics" +
                (legacyGame.variants.length > 1 ? " · Variant " + (index + 1) : "");
            const details = itemDetailsSection(panel, label, Object.entries(variant.fields), variant.source, index === 0);
            if (variant.additional_source) details.appendChild(sourceLink(variant.additional_source, "Attack damage and effects source"));
        });
    }
    addLegacyDmgDetails(panel, item);
    const familyEntries = magicFamilies && magicFamilies.records[item.id] || [];
    const entries = (curated && curated.records[item.id] || [])
        .concat(publishedFacts && publishedFacts.records[item.id] || [], familyEntries,
            coreArmor && coreArmor.public && coreArmor.public[item.id] || [],
            diabloArmor && diabloArmor.records[item.id] || [],
            diabloUniqueArmor && diabloUniqueArmor.records[item.id] || []);
    const hasReviewedCombatRules = entries.some(entry =>
        (entry.status === "published-reference" || entry.profile_kind === "custom-2024-draft") &&
        ["Damage", "Range", "Activation"].every(field => entry.fields[field]));
    if (!hasReviewedCombatRules && !addPublishedCrossReference(panel, item, references, enhancements)) {
        addWeaponProfile(panel, item, weapons);
    }
    entries.forEach((entry, index) => {
        const label = entry.status === "original-draft" ? entry.label + " · DM review" : entry.label;
        const playableDraft = entry.status === "original-draft" &&
            (["Damage", "Range", "Activation"].every(field => entry.fields[field]) ||
                (entry.fields.Training && (entry.fields["Armor class"] || entry.fields["Armor class bonus"])) ||
                (item.type === "spellcasting-focus" && entry.fields.Activation && entry.fields["Special powers"]) ||
                (entry.profile_kind === "adapted-protective-garment" && entry.fields["Use as armor"] && entry.fields["Special powers"]));
        const details = itemDetailsSection(panel, label, Object.entries(entry.fields), entry.source,
            playableDraft || (entry.status !== "original-draft" && (entries.length <= 12 || index === 0)));
        if (entry.rules_source) {
            details.appendChild(sourceLink(entry.rules_source, "Read published rules"));
        }
        if (entry.related_item) {
            const button = element("button", entry.related_item.label);
            button.addEventListener("click", () => inspect(entry.related_item.id, returnFocus));
            details.appendChild(button);
        }
    });
    const bg3Record = bg3 && bg3.records[item.id];
    if (bg3Record && !entries.some(entry => entry.status === "source-reported")) {
        addBg3ItemDetails(panel, item.id, bg3Record, bg3.effects || {}, bg3Armor || {});
    }
    if (item.ruleset === "bg3" && item.type === "weapon") {
        const variants = (item.mechanics || {}).bg3_template_variants || [];
        const locations = Array.from(new Set(variants.map(variant => variant.facts["where to find location"]).filter(Boolean)));
        if (locations.length) {
            const acquisition = itemDetailsSection(panel, "Acquisition", [], (item.provenance || {}).source_url);
            locations.forEach(title => acquisition.appendChild(sourceLink(wikiLink(title), title)));
        }
    }
    if (!entries.some(entry => entry.profile_kind === "adapted-barding" || entry.dexterity_cap_override
        || (entry.profile_kind === "adapted-source-armor" && entry.stealth_exception))) {
        addPublishedEquipment(panel, item, publishedArmor, coreArmor);
    }
    addSpellReference(panel, item, spells);
    add2024Crafting(panel, item);
    addSrdEquipmentUse(panel, item, returnFocus);
    if (item.source_id !== "open5e-srd-2024") addRecordedEncounters(panel, item);
    return Boolean(entries.length || bg3Record || panel.children.length);
}
