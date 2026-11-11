"use strict";

const blinskyIds = [
    "curse-of-strahd-reference:b7a9e5e81019ad5a",
    "curse-of-strahd-reference:6c523a2cdcc1fa0f",
    "curse-of-strahd-reference:456b7caa552725c4",
    "curse-of-strahd-reference:7028e422a33da61f",
    "curse-of-strahd-reference:ca5fa7c529a2588b",
    "curse-of-strahd-reference:58792ffb9029e359"
];
const toyBasket = new Map();
let shopStock = [];

function coins(copper) {
    return [[Math.floor(copper / 100), "gp"], [Math.floor(copper / 10) % 10, "sp"], [copper % 10, "cp"]]
        .filter(([count]) => count).map(([count, unit]) => count + " " + unit).join(" ") || "0 cp";
}

function renderBasket() {
    const basket = byId("basket-items");
    basket.textContent = "";
    let totalCopper = 0;
    shopStock.forEach(item => {
        const quantity = toyBasket.get(item.id) || 0;
        if (!quantity) return;
        const row = element("div", "", "basket-row");
        row.appendChild(element("span", quantity + " × " + item.name));
        const remove = element("button", "Remove one");
        remove.setAttribute("aria-label", "Remove one " + item.name);
        remove.addEventListener("click", () => {
            if (quantity === 1) toyBasket.delete(item.id);
            else toyBasket.set(item.id, quantity - 1);
            renderBasket();
            const next = basket.querySelector("button") || byId("shop-stock").querySelector(".shop-add");
            if (next) next.focus();
        });
        row.appendChild(remove);
        basket.appendChild(row);
        totalCopper += quantity * item.shopCopper;
    });
    byId("basket-total").textContent = toyBasket.size ? "Total · " + coins(totalCopper) : "Basket is empty.";
    byId("clear-basket").hidden = !toyBasket.size;
}

function openShop() {
    dismissInspection();
    const shop = byId("blinsky-shop");
    const stock = byId("shop-stock");
    stock.textContent = "";
    shopStock = blinskyIds.map(id => JSON.parse(Armory.item(id))).filter(item =>
        item.name && item.market_price && item.market_price.method === "source-retail"
    );
    shopStock.forEach(item => {
        item.shopCopper = Math.round(Number(item.market_price.base_buy_gp) * 100);
        const tile = element("article", "", "shop-tile");
        const inspectButton = element("button", "", "card");
        inspectButton.appendChild(icon(item.image && item.image.path));
        inspectButton.appendChild(element("strong", item.name));
        inspectButton.appendChild(element("small", coins(item.shopCopper)));
        inspectButton.addEventListener("click", () => inspect(item.id, inspectButton));
        tile.appendChild(inspectButton);
        const add = element("button", "Add to basket", "shop-add");
        add.setAttribute("aria-label", "Add " + item.name + " to basket");
        add.addEventListener("click", () => {
            toyBasket.set(item.id, (toyBasket.get(item.id) || 0) + 1);
            renderBasket();
        });
        tile.appendChild(add);
        stock.appendChild(tile);
    });
    document.querySelector("main > .shelf").hidden = true;
    shop.hidden = false;
    renderBasket();
    byId("leave-shop").focus();
    window.scrollTo(0, 0);
}

function closeShop() {
    if (byId("blinsky-shop").hidden) return false;
    dismissInspection();
    byId("blinsky-shop").hidden = true;
    document.querySelector("main > .shelf").hidden = false;
    byId("visit-blinsky").focus();
    return true;
}

function setupShop() {
    byId("visit-blinsky").addEventListener("click", openShop);
    byId("leave-shop").addEventListener("click", closeShop);
    byId("clear-basket").addEventListener("click", () => {
        toyBasket.clear();
        renderBasket();
        const add = byId("shop-stock").querySelector(".shop-add");
        if (add) add.focus();
    });
}
