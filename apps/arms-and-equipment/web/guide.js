"use strict";
const byId = id => document.getElementById(id);
const groups = {
    All: [],
    Weapons: ["weapon","ammunition"],
    Armor: ["armor","shield","helmet","boots","gloves","cloak","belt"],
    Magic: [],
    Consumables: ["potion","scroll","poison","consumable","consumables","food","alchemy","alchemical-ingredients","alchemical-extracts"],
    Gear: ["adventuring-gear","gear","tools","container","clothing","book","key","instrument","furnishing","misc","gem","material","trade-good","dye","other"],
    Construction: ["construction-component","structure","mount","waterborne-vehicle","land-vehicle","air-vehicle","flying-vehicle"]
};
const editionNames = {"dnd-2024":"D&D 2024","dnd-2014":"D&D 2014","adnd-1e":"AD&D 1e","adnd-2e":"AD&D 2e","dnd-3.5":"D&D 3.5","dnd-4e":"D&D 4e","bg3":"Baldur’s Gate 3"};
const editions = ["dnd-2024","dnd-2014","adnd-1e","adnd-2e","dnd-2e","dnd-becmi","dnd-3e","dnd-3.5","dnd-4e","bg3","game-reference","third-party-5e","a5e","dnd-edition-unverified","homebrew-reference"];
const facets = {};
const sources = {};
const entities = {};
const grid = byId("items");
const inspection = byId("inspection");
const placeholder = inspection.firstElementChild.cloneNode(true);
let category = "All";
let initial = "";
let selected = "";
let offset = 0;
let total = 0;
let searchId = 0;
let searchContext;
let displayedCriteria = "";
let appliedBudget = {minimum:null, maximum:null};
let timer;
let returnFocus;

function pretty(value) {
    return String(value || "").replace(/[-_]/g, " ").replace(/^./, letter => letter.toUpperCase());
}
function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
}
function icon(path) {
    const image = element("img");
    image.alt = "";
    image.src = /^images\/types\/[a-z-]+\.svg$/.test(path || "") ? path : "images/types/gear.svg";
    return image;
}
function facet(id, title, options) {
    const label = element("label", title);
    const select = element("select");
    select.appendChild(new Option("Any", ""));
    options.forEach(row => select.appendChild(new Option(row[1], row[0])));
    select.addEventListener("change", () => search(false));
    label.appendChild(select);
    byId("facets").appendChild(label);
    facets[id] = select;
    select.dataset.label = title;
}
function showFilters(open) {
    byId("filters").hidden = !open;
    byId("filter-toggle").setAttribute("aria-expanded", String(open));
}
function buyBudget() {
    const min = byId("price-min");
    const max = byId("price-max");
    const error = byId("budget-error");
    const minimum = min.value === "" ? null : Math.round(Number(min.value) * 100);
    const maximum = max.value === "" ? null : Math.round(Number(max.value) * 100);
    const invalid = !min.validity.valid || !max.validity.valid || (minimum !== null && maximum !== null && minimum > maximum);
    error.textContent = invalid ? "Enter a valid price range. The minimum must be no higher than the maximum." : "";
    error.hidden = !invalid;
    return invalid ? null : {minimum, maximum};
}
function applyBuyBudget() {
    const budget = buyBudget();
    if (!budget) return false;
    appliedBudget = budget;
    return true;
}
function search(append) {
    clearTimeout(timer);
    const budget = appliedBudget;
    if (!append) offset = 0;
    const query = {term:byId("search").value, types:groups[category], initial, sort:byId("sort").value, offset:offset, tags:[]};
    Object.keys(facets).forEach(key => query[key] = facets[key].value);
    if (budget.minimum !== null) query.minBuyCopper = budget.minimum;
    if (budget.maximum !== null) query.maxBuyCopper = budget.maximum;
    if (category === "Magic") query.tags.push("magic");
    if (query.property) query.tags.push("property:" + query.property);
    if (query.damage) query.tags.push("damage:" + query.damage);
    if (query.enchantment) query.tags.push(query.enchantment);
    const active = Object.keys(facets).filter(key => facets[key].value);
    const chips = byId("active-filters");
    chips.textContent = "";
    const hasBudget = budget.minimum !== null || budget.maximum !== null;
    const activeCount = active.length + Number(hasBudget);
    chips.hidden = !activeCount;
    byId("filter-toggle").textContent = activeCount ? "Filters (" + activeCount + ")" : "Filters";
    active.forEach(key => {
        const select = facets[key];
        const label = select.options[select.selectedIndex].text;
        const chip = element("button", label + " ×");
        chip.setAttribute("aria-label", "Remove " + select.dataset.label + " filter: " + label);
        chip.addEventListener("click", () => {
            select.value = "";
            search(false);
            byId("filter-toggle").focus();
        });
        chips.appendChild(chip);
    });
    if (hasBudget) {
        const parts = [budget.minimum !== null ? "from " + budget.minimum / 100 + " gp" : "",
            budget.maximum !== null ? "up to " + budget.maximum / 100 + " gp" : ""];
        const chip = element("button", "Buy " + parts.filter(Boolean).join(" · ") + " ×");
        chip.setAttribute("aria-label", "Remove buy price filter");
        chip.addEventListener("click", () => {
            byId("price-min").value = "";
            byId("price-max").value = "";
            applyBuyBudget();
            search(false);
            byId("filter-toggle").focus();
        });
        chips.appendChild(chip);
    }
    searchContext = {append, query, criteria:JSON.stringify({...query, sort:undefined, offset:undefined})};
    grid.setAttribute("aria-busy", "true");
    byId("more").disabled = true;
    byId("status").textContent = append ? "Loading more entries…" : "Searching the catalog…";
    Armory.search(++searchId, JSON.stringify(query));
}
window.receiveSearch = function (id, payload) {
    if (id !== searchId) return;
    const {append, query, criteria} = searchContext;
    const result = JSON.parse(payload);
    grid.setAttribute("aria-busy", "false");
    byId("more").disabled = false;
    if (!append) grid.textContent = "";
    byId("more").hidden = true;
    if (result.error) {
        byId("status").textContent = result.error;
        return;
    }
    if (!append) {
        if (criteria !== displayedCriteria && selected && !result.items.some(row => row.id === selected)) {
            dismissInspection();
        }
        displayedCriteria = criteria;
    }
    if (!append) total = result.total;
    byId("status").textContent = total ? total.toLocaleString() + " entries" : "No entries match these filters.";
    if (!result.fullText && query.term && !query.scope) byId("status").textContent += " · Name search";
    const cards = document.createDocumentFragment();
    result.items.forEach((row, index) => {
        const button = element("button", "", "card");
        button.dataset.id = row.id;
        if (row.rarity) button.dataset.rarity = row.rarity;
        button.setAttribute("aria-pressed", String(row.id === selected));
        const art = icon(row.image);
        if (index >= 15) art.setAttribute("loading", "lazy");
        button.appendChild(art);
        button.appendChild(element("strong", row.name));
        const baseCost = query.sort.startsWith("price-")
            ? (Number(row.price_copper) / 100).toLocaleString() + " gp" : "";
        button.appendChild(element("small", [pretty(row.rarity), editionNames[row.ruleset] || pretty(row.ruleset), baseCost].filter(Boolean).join(" · ")));
        button.addEventListener("click", () => inspect(row.id, button));
        cards.appendChild(button);
    });
    grid.appendChild(cards);
    offset += result.items.length;
    byId("more").hidden = offset >= total;
};
function dismissInspection() {
    if (!selected) return false;
    selected = "";
    inspection.classList.remove("active");
    inspection.textContent = "";
    inspection.appendChild(placeholder.cloneNode(true));
    Array.from(grid.children).forEach(card => card.setAttribute("aria-pressed", "false"));
    if (returnFocus && returnFocus.isConnected) returnFocus.focus();
    return true;
}
window.closeInspection = () => dismissInspection() || closeShop();

function inspect(id, trigger) {
    const item = JSON.parse(Armory.item(id));
    if (!item.name) {
        byId("status").textContent = item.error || "This entry is unavailable.";
        return;
    }
    selected = id;
    returnFocus = trigger;
    Array.from(grid.children).forEach(card => card.setAttribute("aria-pressed", String(card.dataset.id === id)));
    inspection.textContent = "";
    inspection.classList.add("active");
    inspection.scrollTop = 0;
    const top = element("div", "", "inspect-top");
    top.appendChild(icon(item.image && item.image.path));
    const close = element("button", "Close");
    close.addEventListener("click", dismissInspection);
    const controls = element("div", "", "inspect-controls");
    const copy = element("button", "Copy entry");
    controls.appendChild(copy);
    controls.appendChild(close);
    top.appendChild(controls);
    inspection.appendChild(top);
    inspection.appendChild(element("h2", item.name));
    const classification = [pretty(item.type), pretty(item.rarity), editionNames[item.ruleset] || pretty(item.ruleset)].filter(Boolean).join(" · ");
    inspection.appendChild(element("p", classification, "meta"));
    const mechanics = item.mechanics || {};
    const weapon = mechanics.weapon || {};
    const fields = mechanics.source_fields || {};
    const damage = weapon.damage_dice ? "Damage " + weapon.damage_dice + " " + (weapon.damage_type || "") : "";
    const properties = (item.tags || []).filter(tag => tag.indexOf("property:") === 0).map(tag => pretty(tag.slice(9)));
    const ac = Number(fields.armor_class) > 0 ? "Armor class " + fields.armor_class : "";
    const propertiesText = [damage, ac, properties.join(", ")].filter(Boolean).join(" · ");
    if (propertiesText) inspection.appendChild(element("p", propertiesText, "rule"));
    const status = [pretty(item.content_status), pretty(item.tabletop_status)].filter(Boolean).join(" · ");
    if (status) inspection.appendChild(element("p", status, "meta"));
    const price = item.market_price;
    const priceRows = price ? [
        ["Base cost", price.base_cost_gp + " gp"],
        ["Base buy", price.base_buy_gp + " gp"],
        ["Base sell", price.base_sell_gp + " gp"]
    ] : [];
    if (price && price.decoration) priceRows.push(["Cosmetic premium", "+" + price.decoration.premium_gp + " gp included"]);
    if (price) {
        inspection.appendChild(element("h3", "Value"));
        statList(inspection, priceRows);
        const pricing = element("details", "", "weapon-feature");
        pricing.appendChild(element("summary", price.method_label));
        pricing.appendChild(element("p", [pretty(price.economy_id), price.basis, price.scope].filter(Boolean).join(" · "), "meta"));
        if (price.decoration) {
            const decoration = price.decoration;
            pricing.appendChild(element("p", decoration.label + " · Physical equipment value " + decoration.physical_base_gp + " gp", "meta"));
            if (decoration.source_url) pricing.appendChild(sourceLink(decoration.source_url, "3.5e masterwork pricing"));
            if (decoration.base_source_url) pricing.appendChild(sourceLink(decoration.base_source_url, "3.5e base equipment price"));
        }
        const quoteBasis = price.policy === "construction-appraisal"
            ? "Buy is an installation or commissioning estimate. Sell is a resale or salvage appraisal."
            : price.policy === "source-resale-and-bg3-buy"
                ? "Sell uses the source’s resale benchmark. Buy uses the neutral BG3-style estimate."
                : price.policy === "source-retail-and-bg3-sell"
                    ? "Buy uses the source’s retail price. Sell uses the neutral BG3-style estimate."
                    : "Buy and sell use the BG3-style multiplier at neutral attitude and +0 Persuasion.";
        pricing.appendChild(element("p", quoteBasis, "meta"));
        if (price.appraisal_only) pricing.appendChild(element("p", "Indicative appraisal. Availability and resale depend on the campaign.", "meta"));
        inspection.appendChild(pricing);
    }
    const bg3Weapon = item.ruleset === "bg3" && item.type === "weapon";
    const description = feetText(item.description || (mechanics.reference_metadata || {}).source_note || "");
    if (description) inspection.appendChild(element("p", description, "detail-description"));
    const rules = element("section");
    inspection.appendChild(rules);
    if (bg3Weapon) {
        addBg3Weapon(rules, item, null);
        bg3WeaponRules.then(supplement => {
            if (rules.isConnected && supplement) addBg3Weapon(rules, item, supplement);
        });
    } else {
        addTabletopWeapon(rules, item);
    }
    const extra = element("section");
    inspection.appendChild(extra);
    itemDetails.then(supplements => {
        if (!extra.isConnected) return;
        const present = addItemDetails(extra, item, supplements);
        if (!present && !bg3Weapon && !description && !rules.children.length) {
            extra.appendChild(element("p", "Source index entry · Rules have not been verified for this edition.", "meta"));
        }
    });
    inspection.appendChild(element("h3", "Source"));
    const source = sources[item.source_id] || item.source_id;
    const sourceRow = element("p", "", "meta");
    const sourceUrl = (item.provenance || {}).source_url;
    sourceRow.appendChild(sourceLink(sourceUrl, source));
    inspection.appendChild(sourceRow);
    if (item.ruleset === "dnd-2024" && item.type === "weapon") {
        const rulesLink = element("p", "", "meta");
        rulesLink.appendChild(sourceLink("https://www.dndbeyond.com/sources/dnd/br-2024/equipment", "2024 equipment rules"));
        inspection.appendChild(rulesLink);
    }
    const labels = (item.associations || []).filter(a => entities[a.entity_id]).map(a => entities[a.entity_id] + " (" + pretty(a.role) + ")");
    if (labels.length) inspection.appendChild(element("p", Array.from(new Set(labels)).join(" · "), "meta"));
    const details = element("details");
    details.appendChild(element("summary", "Source references and changes"));
    const research = item.research_metadata || {};
    (research.source_refs || []).slice(0, 30).forEach(ref => {
        if (!ref.url) return;
        const citation = element("p", "", "meta");
        citation.appendChild(sourceLink(ref.url, ref.label || ref.url));
        details.appendChild(citation);
    });
    const changes = research.change_log || research.changes || [];
    if (Array.isArray(changes)) changes.forEach(change => {
        const value = typeof change === "string" ? change : change.description || change.note || change.summary;
        if (value) details.appendChild(element("p", value, "meta"));
    });
    inspection.appendChild(details);
    const noteLabel = element("label", "Field notes");
    noteLabel.htmlFor = "item-note";
    const note = element("textarea");
    note.id = "item-note";
    note.maxLength = 4000;
    note.value = Armory.note(id);
    note.addEventListener("input", () => Armory.saveNote(id, note.value));
    inspection.appendChild(noteLabel);
    inspection.appendChild(note);
    const actions = element("div", "", "actions");
    const exportText = () => [item.name, classification, propertiesText, status, description,
        Array.from(rules.querySelectorAll("h3,h4,summary,p,dt")).concat(
            Array.from(extra.querySelectorAll("h3,h4,summary,p,dt"))
        ).map(node => {
            return node.tagName === "DT" ? node.textContent + " · " + node.nextElementSibling.textContent : node.textContent;
        }).join("\n"),
        price ? priceRows.map(([label, value]) => label + " · " + value).concat(price.method_label).join("\n") : "",
        ["Source · " + source, sourceUrl].filter(Boolean).join("\n"),
        note.value.trim() ? "Field notes\n" + note.value.trim() : ""].filter(Boolean).join("\n\n");
    const copyStatus = element("p", "", "meta");
    copyStatus.setAttribute("role", "status");
    top.insertAdjacentElement("afterend", copyStatus);
    copy.addEventListener("click", () => {
        copyStatus.textContent = Armory.copyEntry(item.name, exportText()) ? "Entry copied." : "Could not copy the entry.";
    });
    const share = element("button", "Share entry");
    share.addEventListener("click", () => Armory.share(item.name, exportText()));
    actions.appendChild(share);
    const pdf = element("button", "Share PDF");
    const message = element("p", "", "meta");
    message.setAttribute("role", "status");
    pdf.addEventListener("click", () => message.textContent = Armory.sharePdf(item.name, exportText()));
    actions.appendChild(pdf);
    inspection.appendChild(actions);
    inspection.appendChild(message);
    close.focus();
}

function syncCategories() {
    Array.from(byId("categories").children).forEach(button => {
        button.setAttribute("aria-pressed", String(button.textContent === category));
    });
}
function setInitial(value) {
    initial = /^[a-z#]$/.test(value) ? value : "";
    const strip = byId("alphabet");
    Array.from(strip.children).forEach(button => {
        const active = button.dataset.initial === initial;
        button.setAttribute("aria-pressed", String(active));
        if (!active) return;
        const stripBounds = strip.getBoundingClientRect();
        const buttonBounds = button.getBoundingClientRect();
        if (buttonBounds.left < stripBounds.left) strip.scrollLeft -= stripBounds.left - buttonBounds.left;
        if (buttonBounds.right > stripBounds.right) strip.scrollLeft += buttonBounds.right - stripBounds.right;
    });
}
function setListView(list) {
    grid.classList.toggle("list", list);
    byId("view-toggle").textContent = list ? "Grid view" : "List view";
    byId("view-toggle").setAttribute("aria-pressed", String(list));
}
function applyDefaults() {
    const defaults = JSON.parse(Armory.defaults());
    Object.keys(facets).forEach(key => {
        const select = facets[key];
        const saved = (defaults.facets || {})[key];
        select.value = Array.from(select.options).some(option => option.value === saved) ? saved : "";
    });
    category = Object.keys(groups).includes(defaults.category) ? defaults.category : "All";
    byId("sort").value = Array.from(byId("sort").options).some(option => option.value === defaults.sort)
        ? defaults.sort : "relevance";
    setInitial(defaults.initial);
    byId("price-min").value = defaults.minBuyGp || "";
    byId("price-max").value = defaults.maxBuyGp || "";
    if (!applyBuyBudget()) appliedBudget = {minimum:null, maximum:null};
    setListView(defaults.list === true);
    syncCategories();
}
function start() {
    const metadata = JSON.parse(Armory.metadata());
    if (metadata.error) {
        byId("status").textContent = metadata.error;
        return;
    }
    metadata.sources.forEach(row => sources[row.id] = row.name);
    metadata.taxonomy.entities.forEach(row => entities[row.id] = row.label);
    setupShop();
    facet("scope", "Search in", [["name","Item name"],["exact","Exact item name"]]);
    facets.scope.options[0].text = "All indexed text";
    facet("proficiency", "Class proficiency or training", [["rogue-2024","Rogue · 2024"],["fighter-2024","Fighter · 2024"]]);
    facet("enchantment", "Magic status", [["magic","Magic"],["mundane","Mundane"]]);
    facet("damage", "Damage type", ["acid","bludgeoning","cold","fire","force","lightning","necrotic","piercing","poison","psychic","radiant","slashing","thunder"].map(id => [id, pretty(id)]));
    facet("ruleset", "Rules edition", editions.map(id => [id, editionNames[id] || pretty(id)]));
    facet("rarity", "Rarity", ["common","uncommon","rare","very-rare","legendary","artifact","varies"].map(id => [id, pretty(id)]));
    facet("property", "Weapon property", [
        ["ammunition", "Ammunition"], ["cant-dual-wield", "Can’t dual wield"], ["dippable", "Dippable"],
        ["enchanted", "Enchanted"], ["finesse", "Finesse"], ["heavy", "Heavy"], ["light", "Light"],
        ["loading", "Loading"], ["melee", "Melee"], ["one-handed", "One-handed"], ["ranged", "Ranged"],
        ["reach", "Reach"], ["special", "Special"], ["thrown", "Thrown"],
        ["two-handed", "Two-handed"], ["versatile", "Versatile"]
    ]);
    facet("source", "Source", metadata.sources.filter(row => row.record_count > 0).map(row => [row.id,row.name]).sort((a,b) => a[1].localeCompare(b[1])));
    ["setting","region","culture"].forEach(kind => facet(kind, pretty(kind), metadata.taxonomy.entities
        .filter(row => row.kind === kind).map(row => [row.id,row.label]).sort((a,b) => a[1].localeCompare(b[1]))));
    Object.keys(groups).forEach(name => {
        const tab = element("button", name);
        tab.setAttribute("aria-pressed", String(name === category));
        tab.addEventListener("click", () => {
            category = name;
            syncCategories();
            search(false);
        });
        byId("categories").appendChild(tab);
    });
    ["", ..."abcdefghijklmnopqrstuvwxyz", "#"].forEach(value => {
        const button = element("button", value ? value.toUpperCase() : "A–Z");
        button.dataset.initial = value;
        button.setAttribute("aria-label", value === "#" ? "Numbers and other initials"
            : value ? "Starts with " + value.toUpperCase() : "All initials");
        button.addEventListener("click", () => {
            setInitial(value);
            search(false);
        });
        byId("alphabet").appendChild(button);
    });
    byId("search").addEventListener("input", () => {
        clearTimeout(timer);
        searchId++;
        byId("more").disabled = true;
        timer = setTimeout(() => search(false), 100);
    });
    byId("filter-toggle").addEventListener("click", () => showFilters(byId("filters").hidden));
    ["price-min", "price-max"].forEach(id => byId(id).addEventListener("change", () => {
        if (applyBuyBudget()) search(false);
    }));
    byId("reset").addEventListener("click", () => {
        Object.keys(facets).forEach(key => facets[key].value = "");
        byId("price-min").value = "";
        byId("price-max").value = "";
        applyBuyBudget();
        setInitial("");
        search(false);
    });
    byId("sort").addEventListener("change", () => search(false));
    byId("view-toggle").addEventListener("click", () => {
        setListView(!grid.classList.contains("list"));
    });
    byId("more").addEventListener("click", () => search(true));
    document.addEventListener("keydown", event => { if (event.key === "Escape") window.closeInspection(); });
    byId("save-defaults").addEventListener("click", () => {
        const values = {};
        Object.keys(facets).forEach(key => values[key] = facets[key].value);
        if (!buyBudget()) return;
        const saved = Armory.saveDefaults(JSON.stringify({facets:values, category:category, initial,
            minBuyGp:byId("price-min").value, maxBuyGp:byId("price-max").value,
            sort:byId("sort").value, list:grid.classList.contains("list")}));
        byId("default-status").textContent = saved ? "Saved for the next launch." : "Defaults could not be saved.";
    });
    byId("restore-defaults").addEventListener("click", () => {
        applyDefaults();
        search(false);
        byId("default-status").textContent = "Defaults applied.";
    });
    byId("forget-defaults").addEventListener("click", () => {
        const cleared = Armory.saveDefaults("{}");
        byId("default-status").textContent = cleared ? "Saved defaults removed." : "Defaults could not be removed.";
    });
    applyDefaults();
    byId("version").textContent = "Catalog " + metadata.manifest.content_version;
    requestAnimationFrame(() => setTimeout(() => search(false), 0));
}
if (window.Armory) requestAnimationFrame(() => setTimeout(start, 0));
