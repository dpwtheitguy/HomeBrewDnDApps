"use strict";

const bg3WeaponRules = fetch("bg3-weapon-rules.json")
    .then(response => response.ok ? response.json() : null)
    .catch(() => null);

function sourceLink(url, label) {
    if (typeof url !== "string" || !/^https?:\/\//i.test(url)) return element("span", label || url);
    const link = element("a", label || url);
    link.href = url;
    link.addEventListener("click", event => {
        event.preventDefault();
        Armory.openSource(link.href);
    });
    return link;
}

function distanceInFeet(feet, meters) {
    if (feet !== undefined && feet !== null && feet !== "") return feet + " ft";
    if (meters === undefined || meters === null || !/^\d+(?:\.\d+)?$/.test(meters)) return "";
    const converted = Number(meters) * 3.28084;
    return converted === 0 ? "0 ft" : "≈" + (converted < 1 ? Number(converted.toPrecision(2)) : Math.round(converted)) + " ft";
}

function feetText(value) {
    return String(value)
        .replace(/\b\d+(?:\.\d+)?\s*(?:m|metres?|meters?)\s*(?:\(\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)\s*\)|[/·]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)\b)/g,
            (_, parenthetical, paired) => distanceInFeet(parenthetical || paired))
        .replace(/\b(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)\b(?![²³])/g,
            (_, meters) => distanceInFeet("", meters))
        .replace(/\bper (?:metre|meter)\b/g, "per ≈3.3 ft");
}

function effectStatRows(stats, omitted = []) {
    return Object.keys(stats).filter(key => !omitted.includes(key)).reduce((rows, key) => {
        const unit = /^(range|aoe|condition radius) (m|ft)$/.exec(key);
        if (!unit) rows.push([pretty(key), stats[key]]);
        else if (unit[2] === "ft" || !stats[unit[1] + " ft"]) {
            const label = unit[1] === "aoe" ? "Area size" : pretty(unit[1]);
            rows.push([label, distanceInFeet(stats[unit[1] + " ft"], stats[unit[1] + " m"])]);
        }
        return rows;
    }, []);
}

function statList(panel, entries) {
    const list = element("dl", "", "weapon-stats");
    entries.forEach(([name, value]) => {
        if (value === undefined || value === null || value === "") return;
        list.appendChild(element("dt", name));
        const definition = element("dd");
        if (typeof value === "string" && /^https?:\/\/\S+$/i.test(value)) {
            definition.appendChild(sourceLink(value));
        } else {
            definition.textContent = feetText(value);
        }
        list.appendChild(definition);
    });
    if (list.children.length) panel.appendChild(list);
}

function bg3Range(stats) {
    if (stats["melee or ranged"] === "melee") {
        return stats.reach === "yes" ? "Melee · 8 ft" : "Melee · 5 ft";
    }
    if (stats.range === "normal") return "Ranged · 60 ft";
    if (stats.range === "short") return "Ranged · 50 ft";
    return [
        pretty(stats["melee or ranged"]),
        distanceInFeet(stats["range ft"], stats["range m"])
    ].filter(Boolean).join(" · ");
}

const tabletopBases = {
    "mystara:sword-of-karameikos":"longsword",
    "dagger-of-venom":"dagger",
    "dwarven-thrower":"warhammer",
    "javelin-of-lightning":"javelin",
    "mace-of-disruption":"mace",
    "mace-of-smiting":"mace",
    "mace-of-terror":"mace",
    "scimitar-of-speed":"scimitar",
    "trident-of-fish-command":"trident"
};

function addTabletopWeapon(panel, item, profile) {
    let mechanics = item.mechanics || {};
    const srdPrefix = "open5e-srd-2024:srd-2024_";
    const fixedBase = tabletopBases[item.id] || (item.id.indexOf(srdPrefix) === 0 && tabletopBases[item.id.slice(srdPrefix.length)]);
    if (profile || (!mechanics.weapon && (item.base_item_id || fixedBase))) {
        const baseId = profile ? profile.base_id : item.base_item_id || srdPrefix + fixedBase;
        const base = JSON.parse(Armory.item(baseId));
        if (base.mechanics && base.mechanics.weapon) mechanics = base.mechanics;
    }
    const weapon = mechanics.weapon;
    if (!weapon) return;
    const label = profile
        ? (profile.kind === "source-based-2024" ? "2024 profile · source-based" : "2024 profile · DM review")
        : (item.ruleset === "dnd-2024" ? "2024 weapon rules" : "Weapon rules");
    panel.appendChild(element("h3", label));
    const fields = mechanics.source_fields || {};
    const properties = mechanics.properties || [];
    const meleeRange = properties.some(row => row.property && row.property.name === "Reach") ? "10 ft melee" : "5 ft melee";
    statList(panel, [
        ["Base weapon", weapon.name !== item.name ? weapon.name : ""],
        [weapon.name !== item.name ? "Base damage" : "Damage", [weapon.damage_dice, pretty(weapon.damage_type)].filter(Boolean).join(" ")],
        ["Category", weapon.is_simple === true ? "Simple" : weapon.is_simple === false ? "Martial" : ""],
        ["Range", weapon.range > 0 ? weapon.range + (weapon.long_range > weapon.range ? "/" + weapon.long_range : "") + " ft"
            : weapon.document === "srd-2024" ? meleeRange : ""],
        ["Item bonus", profile && Number.isInteger(profile.bonus) ? "+" + profile.bonus + " to attack and damage" : ""],
        ["Weight", Number(fields.weight) > 0 ? Number(fields.weight) + " lb" : ""],
        ["Attunement", item.requires_attunement === true ? "Required" : typeof item.requires_attunement === "string" ? item.requires_attunement : ""]
    ]);
    properties.forEach(row => {
        const property = row.property || {};
        if (!property.name) return;
        const details = element("details", "", "weapon-feature");
        const assignment = row.assignment || {};
        const label = [property.name, property.type === "Mastery" ? "Mastery" : "", assignment.detail].filter(Boolean).join(" · ");
        details.appendChild(element("summary", label));
        if (property.desc) details.appendChild(element("p", feetText(property.desc)));
        panel.appendChild(details);
    });
}

const featureGroups = {
    "passives":"Passives",
    "passives main hand":"Main-hand passives",
    "passives off hand":"Off-hand passives",
    "weapon actions":"Proficiency weapon actions",
    "special weapon actions":"Special weapon actions",
    "condition":"Conditions",
    "special":"Granted abilities"
};

function addBg3Feature(panel, title, catalog, depth) {
    const entry = catalog[title];
    const detail = element("details", "", "weapon-feature");
    detail.appendChild(element("summary", title));
    if (entry && entry.summary) detail.appendChild(element("p", feetText(entry.summary)));
    if (entry) {
        const facts = entry.facts || {};
        statList(detail, effectStatRows(facts, ["variants", "type"]));
        if (entry.extra_damage.length) statList(detail, [["Extra damage", entry.extra_damage.join(" · ")]]);
        if (facts.variants && depth === 0) {
            facts.variants.split(",").forEach(name => addBg3Feature(detail, name.trim(), catalog, 1));
        }
    }
    const url = entry ? "https://bg3.wiki/w/index.php?oldid=" + entry.revision
        : "https://bg3.wiki/wiki/" + encodeURIComponent(title.replace(/ /g, "_"));
    detail.appendChild(sourceLink(url, "Open ability source"));
    panel.appendChild(detail);
}

function addBg3Weapon(panel, item, supplement) {
    const record = supplement && supplement.weapons[item.id];
    const catalog = supplement && supplement.features || {};
    const variants = record ? record.variants : (item.mechanics.bg3_template_variants || []).map(row => ({
        stats: row.facts, features: {}, special_stats: []
    }));
    panel.textContent = "";
    if (!variants.length) return;
    panel.appendChild(element("h3", "Baldur’s Gate 3 weapon rules"));
    variants.forEach((variant, index) => {
        const stats = variant.stats;
        if (variants.length > 1) panel.appendChild(element("h4", stats.name || "Game variant " + (index + 1)));
        const traits = ["finesse","light","heavy","reach","thrown","dippable","ammunition","loading"]
            .filter(key => /^(yes|true|1)$/i.test(stats[key] || "")).map(pretty);
        if (/^(y|yes|true|1)$/i.test(stats["can't dual wield"] || "")) traits.push("Can’t dual wield");
        statList(panel, [
            ["Damage", [stats.damage, stats["damage type"]].filter(Boolean).join(" ")],
            ["Two-handed damage", [stats["versatile damage"], stats["versatile damage"] && stats["damage type"]].filter(Boolean).join(" ")],
            ["Enchantment", stats.enchantment],
            ["Weapon", [stats.category, stats.type, stats.handedness].filter(Boolean).map(pretty).join(" · ")],
            ["Range", bg3Range(stats)],
            ["Weight", stats["weight kg"] ? stats["weight kg"] + " kg" : ""],
            ["Properties", traits.join(", ")],
            ["Other effects", variant.special_stats.join(" · ")]
        ]);
        Object.keys(featureGroups).forEach(key => {
            const titles = variant.features[key] || [];
            if (!titles.length) return;
            panel.appendChild(element("h4", featureGroups[key]));
            titles.forEach(title => addBg3Feature(panel, title, catalog, 0));
        });
        if (variant.unparsed_special) panel.appendChild(element("p", "See the linked game source for additional effects.", "meta"));
    });
    if (record) panel.appendChild(sourceLink("https://bg3.wiki/w/index.php?oldid=" + record.revision, "Open weapon rules source"));
}
