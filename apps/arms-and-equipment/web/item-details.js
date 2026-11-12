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
    loadSupplement("diablo-2-unique-armor-facts.json")
]);
const equipmentRulesUrl = "https://www.dndbeyond.com/sources/dnd/br-2024/equipment";
const magicItemRulesUrl = "https://www.dndbeyond.com/sources/dnd/br-2024/magic-items";
const scribing = [[1,15],[1,25],[3,100],[5,150],[10,1000],[25,1500],[40,10000],[50,12500],[60,15000],[120,50000]];
const magicCrafting = {common:[5,50],uncommon:[10,200],rare:[50,2000],"very-rare":[125,20000],legendary:[250,100000]};

function wikiLink(title) {
    return "https://bg3.wiki/wiki/" + title.split("#").map(part => encodeURIComponent(part.replace(/ /g, "_"))).join("#");
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

function addBg3ItemDetails(panel, record, effects, armorRules) {
    record.variants.forEach((variant, index) => {
        const stats = variant.stats;
        const facts = variant.facts;
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

function spellReference(panel, spell, source, originalEdition) {
    const details = itemDetailsSection(panel, "2024 spell reference · " + spell.name, [
        ["Spell level", spell.level === 0 ? "Cantrip" : spell.level],
        ["Casting time", pretty(spell.casting_time)],
        ["Reaction trigger", spell.reaction_condition],
        ["Range", spell.range_text],
        ["Area", [pretty(spell.shape_type), spell.shape_size, spell.shape_size_unit].filter(Boolean).join(" ")],
        ["Duration", spell.duration],
        ["Concentration", spell.concentration ? "Required" : ""],
        ["Damage", [spell.damage_roll, (spell.damage_types || []).map(pretty).join(", ")].filter(Boolean).join(" ")],
        ["Saving throw", pretty(spell.saving_throw_ability)]
    ], source, true);
    details.appendChild(element("p", feetText(spell.desc)));
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
        const casting = /\bcast\s+(?:the\s+)?/g;
        let match;
        while ((match = casting.exec(text))) {
            const tail = text.slice(casting.lastIndex);
            const found = names.find(candidate => tail.startsWith(candidate) && !/[a-z]/.test(tail[candidate.length] || ""));
            if (found) matches.add(found);
        }
        matches.forEach(found => spellReference(panel, spells.spells[found], spells.srd, item.ruleset));
        return;
    }
    const spell = spells.spells[name.toLowerCase()];
    const level = spell ? spell.level : inscribed.level;
    const timeCost = Number.isInteger(level) && scribing[level];
    if (spell) {
        spellReference(panel, spell, spells.srd, item.ruleset);
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

function addItemDetails(panel, item, supplements) {
    const [bg3, curated, spells, weapons, references, legacyGames, diabloWeapons, bg3Availability, enhancements,
        diabloUniques, publishedFacts, publishedArmor, bg3Armor, coreArmor, magicFamilies, diabloArmor,
        diabloUniqueArmor] = supplements;
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
                (entry.fields.Training && (entry.fields["Armor class"] || entry.fields["Armor class bonus"])));
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
        addBg3ItemDetails(panel, bg3Record, bg3.effects || {}, bg3Armor || {});
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
    addRecordedEncounters(panel, item);
    return Boolean(entries.length || bg3Record || panel.children.length);
}
