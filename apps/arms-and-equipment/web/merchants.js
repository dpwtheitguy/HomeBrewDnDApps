"use strict";

const merchantShops = {
    bildrath: {
        name: "Bildrath’s Mercantile",
        location: "Village of Barovia · Curse of Strahd",
        policy: "Select adventuring gear under 25 gp at its 2014 list price. Bildrath charges ten times that price and won’t haggle.",
        source: "https://dnd5.kwidz.ca/Adventures/Return%20to%20Ravenloft/Curse%20of%20Strahd%20%281-10%29.pdf#page=44",
        sourceLabel: "Curse of Strahd · Area E1",
        originalPrices: {rope: 100, torch: 1, rations: 50, oil: 10, backpack: 200, bedroll: 100,
            waterskin: 20, tinderbox: 50, crowbar: 200, "lantern-hooded": 500, manacles: 200},
        staples: ["rope", "torch", "rations", "oil"],
        rotating: [["backpack", "bedroll"], ["waterskin", "tinderbox"], ["crowbar", "lantern-hooded", "manacles"]]
    },
    budget: {
        name: "Market Provisioner",
        location: "Thyatis City · Mystara · Budget",
        policy: "An original shop for everyday supplies and inexpensive weapons. Prices are 90% of the 2024 list value.",
        rate: 90,
        staples: ["rations", "torch", "dagger"],
        rotating: [["rope", "crowbar"], ["bedroll", "backpack"], ["waterskin", "quarterstaff"]]
    },
    standard: {
        name: "City Outfitter",
        location: "Thyatis City · Mystara · Standard",
        policy: "An original shop for adventuring kits, weapons, and armor. Prices use the 2024 list value.",
        rate: 100,
        staples: ["shield", "longsword", "chain-shirt"],
        rotating: [["shortbow", "light-crossbow"], ["scale-mail", "studded-leather-armor"], ["lantern-hooded", "potion-of-healing"]]
    },
    premium: {
        name: "Imperial Armorer",
        location: "Thyatis City · Mystara · Premium",
        policy: "An original shop for high-end armor and imported wares. Prices are 125% of the 2024 list value.",
        rate: 125,
        staples: ["plate-armor", "breastplate", "spyglass"],
        rotating: [["half-plate-armor", "splint-armor"], ["greatsword", "heavy-crossbow"], ["antitoxin", "potion-of-healing"]]
    }
};

function merchantStockIds(shop, date) {
    // Use the tablet’s civil date, then count days in UTC so DST cannot shift stock.
    const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000);
    return shop.staples.concat(shop.rotating.map((pool, slot) => {
        const week = Math.floor((day + slot * 2) / 7);
        return pool[((week + slot) % pool.length + pool.length) % pool.length];
    }));
}

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
    const shop = merchantShops[byId("merchant-choice").value];
    byId("merchant-name").textContent = shop.name;
    byId("merchant-location").textContent = shop.location;
    byId("merchant-policy").textContent = shop.policy;
    const source = byId("merchant-source");
    source.hidden = !shop.source;
    source.textContent = shop.sourceLabel || "";
    const date = new Date();
    byId("merchant-date").textContent = "Stock for " + date.toLocaleDateString();
    const stock = byId("merchant-stock");
    stock.textContent = "";
    merchantStockIds(shop, date).forEach(slug => {
        const id = "open5e-srd-2024:srd-2024_" + slug;
        const item = JSON.parse(Armory.item(id));
        const price = merchantPrice(shop, slug, item);
        if (!item.name || price === null) return;
        const button = element("button", "", "card");
        button.type = "button";
        button.dataset.id = id;
        button.dataset.copper = String(price);
        button.append(icon(item.image && item.image.path), element("strong", item.name),
            element("small", coins(price)));
        button.addEventListener("click", () => inspect(id, button, {name: shop.name, price}));
        stock.appendChild(button);
    });
    if (!stock.childElementCount) stock.appendChild(element("p", "Stock is unavailable.", "meta"));
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
    byId("open-merchants").addEventListener("click", () => {
        dismissInspection(false);
        byId("catalog-shelf").hidden = true;
        byId("merchants").hidden = false;
        renderMerchant();
        byId("merchant-choice").focus();
        window.scrollTo(0, 0);
    });
    byId("merchant-choice").addEventListener("change", renderMerchant);
    byId("merchant-back").addEventListener("click", closeMerchants);
    byId("merchant-source").addEventListener("click", () => {
        const shop = merchantShops[byId("merchant-choice").value];
        if (shop.source) Armory.openSource(shop.source);
    });
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden && !byId("merchants").hidden && !inspection.classList.contains("active")) renderMerchant();
    });
}
