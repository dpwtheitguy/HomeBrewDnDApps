"use strict";

const trailGear = ["rope", "torch", "rations", "oil", "backpack", "bedroll", "waterskin",
    "tinderbox", "crowbar", "blanket", "bucket", "grappling-hook", "lantern-hooded", "mirror", "sack"];
const fieldWeapons = ["dagger", "handaxe", "mace", "spear", "quarterstaff", "shortbow", "light-crossbow"];
const fieldArmor = ["padded-armor", "leather-armor", "hide-armor", "chain-shirt", "shield"];
const martialWeapons = ["longsword", "rapier", "scimitar", "warhammer", "battleaxe", "longbow"];
const plateArmor = ["breastplate", "half-plate-armor", "splint-armor", "plate-armor", "chain-mail", "scale-mail"];

const merchantShops = {
    bildrath: {
        name: "Bildrath’s Mercantile",
        location: "Village of Barovia · Curse of Strahd",
        policy: "Bildrath stocks adventuring gear below 25 gp at its 2014 list price. He charges ten times that price and won’t haggle.",
        source: "https://dnd5.kwidz.ca/Adventures/Return%20to%20Ravenloft/Curse%20of%20Strahd%20%281-10%29.pdf#page=44",
        sourceLabel: "Curse of Strahd · Area E1",
        originalPrices: {rope: 100, torch: 1, rations: 50, oil: 10, backpack: 200, bedroll: 100,
            waterskin: 20, tinderbox: 50, crowbar: 200, blanket: 50, bucket: 5, "grappling-hook": 200,
            "lantern-hooded": 500, mirror: 500, sack: 1, manacles: 200, chain: 500, candle: 1,
            "ball-bearings": 100, caltrops: 100, ladder: 10, lock: 1000, "lantern-bullseye": 1000,
            "block-and-tackle": 100, "hunting-trap": 500, "clothes-fine": 1500, perfume: 500},
        staples: [...trailGear, "manacles", "chain", "candle", "ball-bearings", "caltrops"],
        surprises: ["ladder", "lock", "lantern-bullseye", "block-and-tackle", "hunting-trap", "clothes-fine", "perfume"]
    },
    budget: {
        name: "Market Provisioner",
        location: "Thyatis City · Mystara · Budget",
        policy: "Everyday supplies and inexpensive weapons at 90% of the catalog base price.",
        rate: 90,
        staples: [...trailGear, ...fieldWeapons, ...fieldArmor],
        surprises: ["potion-of-healing", "antitoxin", "alchemists-fire", "hunting-trap", "dagger-plus-1", "potion-of-climbing"]
    },
    standard: {
        name: "City Outfitter",
        location: "Thyatis City · Mystara · Standard",
        policy: "Adventuring kits, weapons, and armor at the catalog base price.",
        rate: 100,
        staples: [...trailGear, ...fieldWeapons, ...fieldArmor, ...martialWeapons, "scale-mail", "arrows-20", "bolts-20", "potion-of-healing"],
        surprises: ["longsword-plus-1", "shield-plus-1", "potion-of-water-breathing", "potion-of-growth", "potion-of-animal-friendship", "leather-armor-plus-1"]
    },
    premium: {
        name: "Imperial Armorer",
        location: "Thyatis City · Mystara · Premium",
        policy: "High-end arms, armor, and imported wares at 125% of the catalog base price.",
        rate: 125,
        staples: [...martialWeapons, ...plateArmor, "greatsword", "greataxe", "heavy-crossbow", "halberd",
            "glaive", "trident", "shield", "studded-leather-armor", "spyglass", "antitoxin", "smiths-tools", "potion-of-healing"],
        surprises: ["plate-armor-plus-1", "greatsword-plus-1", "shield-plus-1", "potion-of-speed", "potion-of-heroism", "longbow-plus-1"]
    },
    threshold: {
        name: "Rivergate Outfitters",
        location: "Threshold · Karameikos · Mystara",
        policy: "Trail and river supplies at the catalog base price.",
        rate: 100,
        staples: [...trailGear, ...fieldWeapons, "leather-armor", "hide-armor", "shield", "arrows-20",
            "bolts-20", "net", "healers-kit"],
        surprises: ["potion-of-water-breathing", "potion-of-climbing", "spear-plus-1", "potion-of-healing", "potion-of-animal-friendship", "navigators-tools"]
    },
    vallaki: {
        name: "Lantern & Lock",
        location: "Vallaki · Barovia · Ravenloft",
        policy: "Travel supplies and road defenses at 150% of the catalog base price.",
        rate: 150,
        staples: [...trailGear, ...fieldWeapons, ...fieldArmor, "holy-water", "sling", "lock", "manacles", "healers-kit"],
        surprises: ["potion-of-healing", "potion-of-resistance", "mace-plus-1", "shield-plus-1", "potion-of-invisibility", "antitoxin"]
    }
};

const merchantCategories = {
    all: "All", weapon: "Weapons", armor: "Armor & shields", ammunition: "Ammunition",
    potion: "Potions", gear: "Gear", featured: "Daily finds"
};

function merchantCategory(item) {
    if (item.id === "open5e-srd-2024:srd-2024_torch" || item.id === "open5e-srd-2024:srd-2024_oil") return "gear";
    if (item.type === "shield") return "armor";
    return ["weapon", "armor", "ammunition", "potion"].includes(item.type) ? item.type : "gear";
}

function merchantDailyFinds(shopId, date) {
    const pool = merchantShops[shopId].surprises;
    const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000);
    let seed = 2166136261;
    for (const character of shopId + ":" + day) {
        seed = Math.imul(seed ^ character.charCodeAt(0), 16777619);
    }
    const count = 1 + (seed >>> 0) % 3;
    // Rotate the lead find through half the pool. Extra finds come from the other half.
    const leadCount = Math.ceil(pool.length / 2);
    const finds = [pool[((day % leadCount) + leadCount) % leadCount]];
    const extras = pool.slice(leadCount);
    for (let slot = 1; slot < count; slot++) {
        seed = Math.imul(seed ^ slot, 16777619);
        finds.push(extras.splice((seed >>> 0) % extras.length, 1)[0]);
    }
    return finds;
}

let activeMerchantCategory = "all";
let renderedMerchantDate = "";

function merchantPrice(shop, slug, item) {
    if (shop.originalPrices) {
        const original = shop.originalPrices[slug];
        return Number.isFinite(original) && original > 0 && original < 2500 ? original * 10 : null;
    }
    const base = item.market_price && item.market_price.base_cost_gp;
    return base != null && Number(base) > 0 ? Math.round(Number(base) * shop.rate) : null;
}

function renderMerchant() {
    dismissInspection(false);
    const shopId = byId("merchant-choice").value;
    const shop = merchantShops[shopId];
    byId("merchant-name").textContent = shop.name;
    byId("merchant-location").textContent = shop.location;
    byId("merchant-policy").textContent = shop.policy;
    const source = byId("merchant-source");
    source.hidden = !shop.source;
    source.textContent = shop.sourceLabel || "";
    const date = new Date();
    renderedMerchantDate = date.toDateString();
    byId("merchant-date").textContent = "Stock for " + date.toLocaleDateString();
    const stock = byId("merchant-stock");
    stock.textContent = "";
    byId("merchant-categories").querySelectorAll("button").forEach(button => {
        button.setAttribute("aria-pressed", String(button.dataset.category === activeMerchantCategory));
    });
    const featured = merchantDailyFinds(shopId, date);
    for (const slug of featured.concat(shop.staples)) {
        const id = "open5e-srd-2024:srd-2024_" + slug;
        const item = JSON.parse(Armory.item(id));
        const price = merchantPrice(shop, slug, item);
        if (!item.name || price === null) continue;
        const isFeatured = featured.includes(slug);
        const category = merchantCategory(item);
        if (activeMerchantCategory !== "all" && activeMerchantCategory !== category
                && !(activeMerchantCategory === "featured" && isFeatured)) continue;
        const button = element("button", "", "card");
        button.type = "button";
        button.dataset.id = id;
        button.dataset.copper = String(price);
        button.dataset.category = category;
        button.dataset.featured = String(isFeatured);
        button.append(icon(item.image && item.image.path), element("strong", item.name),
            element("small", coins(price)));
        if (isFeatured) button.append(element("small", "Daily find", "merchant-find"));
        button.addEventListener("click", () => inspect(id, button, {name: shop.name, price}));
        stock.appendChild(button);
    }
    if (!stock.childElementCount) stock.appendChild(element("p", "This shop has no stock in this category.", "meta"));
}

function closeMerchants() {
    const page = byId("merchants");
    if (page.hidden) return false;
    dismissInspection(false);
    page.hidden = true;
    byId("catalog-shelf").hidden = false;
    byId("open-merchants").focus();
    return true;
}

function setupMerchants() {
    const categories = byId("merchant-categories");
    Object.entries(merchantCategories).forEach(([id, name]) => {
        const button = element("button", name);
        button.type = "button";
        button.dataset.category = id;
        button.addEventListener("click", () => {
            activeMerchantCategory = id;
            renderMerchant();
        });
        categories.appendChild(button);
    });
    const refreshDate = () => {
        if (!document.hidden && !byId("merchants").hidden && !inspection.classList.contains("active")
                && renderedMerchantDate !== new Date().toDateString()) renderMerchant();
    };
    window.setInterval(refreshDate, 30000);
    document.addEventListener("visibilitychange", refreshDate);
    byId("open-merchants").addEventListener("click", () => {
        dismissInspection(false);
        byId("catalog-shelf").hidden = true;
        byId("merchants").hidden = false;
        renderMerchant();
        byId("merchant-choice").focus();
        window.scrollTo(0, 0);
    });
    byId("merchant-choice").addEventListener("change", () => {
        activeMerchantCategory = "all";
        renderMerchant();
    });
    byId("merchant-back").addEventListener("click", closeMerchants);
    byId("merchant-source").addEventListener("click", () => {
        const shop = merchantShops[byId("merchant-choice").value];
        if (shop.source) Armory.openSource(shop.source);
    });
}
