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
let shopMusicWanted = true;
let shopEyeTimer;
let shopWhisperTimer;
let lastWhisper = 0;
let jackTimer;
let jackTurns = 0;
let lastShopPoint;

function shopIsVisible() {
    return !byId("blinsky-shop").hidden && !document.hidden;
}

function syncShopMusic() {
    const music = byId("shop-music");
    if (shopMusicWanted && shopIsVisible()) {
        music.play().catch(() => {});
    } else {
        music.pause();
        byId("shop-effect").pause();
    }
}

function playShopEffect(file) {
    if (!shopMusicWanted || !shopIsVisible()) return;
    const effect = byId("shop-effect");
    effect.src = file;
    effect.play().catch(() => {});
}

function scheduleShopWhisper() {
    clearTimeout(shopWhisperTimer);
    if (!shopMusicWanted || !shopIsVisible()) return;
    shopWhisperTimer = setTimeout(() => {
        if (byId("jack-reveal").hidden) {
            const choices = [1, 2, 3].filter(clip => clip !== lastWhisper);
            lastWhisper = choices[Math.floor(Math.random() * choices.length)];
            playShopEffect("blinsky-whisper-" + lastWhisper + ".wav");
        }
        scheduleShopWhisper();
    }, 40000 + Math.random() * 10000);
}

function resetJack() {
    clearTimeout(jackTimer);
    jackTurns = 0;
    const box = byId("jack-box");
    box.classList.remove("jack-open");
    box.style.removeProperty("--crank-angle");
    byId("jack-reveal").hidden = true;
    byId("jack-status").textContent = "Turn the crank";
}

function turnJackCrank() {
    if (!byId("jack-reveal").hidden) return;
    const box = byId("jack-box");
    jackTurns += 1;
    box.style.setProperty("--crank-angle", (jackTurns * 360) + "deg");
    if (jackTurns < 3) {
        byId("jack-status").textContent = jackTurns === 1 ? "The gears catch" : "The lid rattles";
        return;
    }
    box.classList.add("jack-open");
    byId("jack-status").textContent = "The jack springs out!";
    byId("jack-reveal").hidden = false;
    playShopEffect("blinsky-jack-pop.wav");
    jackTimer = setTimeout(resetJack, 1650);
}

function pointShopEye() {
    const eye = byId("shop-eye");
    if (eye.hidden) return;
    const bounds = eye.getBoundingClientRect();
    const point = lastShopPoint || {clientX: innerWidth / 2, clientY: innerHeight / 2};
    const dx = point.clientX - (bounds.left + bounds.width / 2);
    const dy = point.clientY - (bounds.top + bounds.height / 2);
    const distance = Math.max(Math.hypot(dx, dy), 1);
    eye.style.setProperty("--gaze-x", 10 * dx / distance + "px");
    eye.style.setProperty("--gaze-y", 4 * dy / distance + "px");
}

function scheduleShopEye() {
    clearTimeout(shopEyeTimer);
    shopEyeTimer = setTimeout(() => {
        const eye = byId("shop-eye");
        eye.style.setProperty("--eye-left", 12 + Math.random() * 76 + "%");
        eye.style.setProperty("--eye-top", 22 + Math.random() * 56 + "%");
        eye.hidden = false;
        pointShopEye();
        scheduleShopEye();
    }, 8000 + Math.random() * 14000);
}

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
    closeMerchants();
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
        inspectButton.addEventListener("click", () => inspect(item.id, inspectButton, {
            name: "Blinsky’s Toys", price: item.shopCopper
        }));
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
    syncShopMusic();
    scheduleShopWhisper();
    scheduleShopEye();
    renderBasket();
    byId("leave-shop").focus();
    window.scrollTo(0, 0);
}

function closeShop() {
    if (byId("blinsky-shop").hidden) return false;
    dismissInspection();
    byId("blinsky-shop").hidden = true;
    syncShopMusic();
    clearTimeout(shopEyeTimer);
    clearTimeout(shopWhisperTimer);
    byId("shop-eye").hidden = true;
    lastShopPoint = null;
    resetJack();
    document.querySelector("main > .shelf").hidden = false;
    byId("visit-blinsky").focus();
    return true;
}

function setupShop() {
    const music = byId("shop-music");
    const musicToggle = byId("shop-music-toggle");
    music.volume = .45;
    byId("shop-effect").volume = .56;
    ["play", "pause", "error"].forEach(event =>
        music.addEventListener(event, () => musicToggle.setAttribute("aria-pressed", String(!music.paused))));
    musicToggle.addEventListener("click", () => {
        shopMusicWanted = music.paused;
        syncShopMusic();
        scheduleShopWhisper();
    });
    document.addEventListener("visibilitychange", () => {
        syncShopMusic();
        scheduleShopWhisper();
        if (document.hidden) resetJack();
    });
    const shop = byId("blinsky-shop");
    ["pointermove", "pointerdown"].forEach(event => shop.addEventListener(event, point => {
        lastShopPoint = point;
        pointShopEye();
    }));
    const eye = byId("shop-eye");
    eye.addEventListener("animationend", () => { eye.hidden = true; });
    byId("jack-crank").addEventListener("click", turnJackCrank);
    byId("visit-blinsky").addEventListener("click", openShop);
    byId("leave-shop").addEventListener("click", closeShop);
    byId("clear-basket").addEventListener("click", () => {
        toyBasket.clear();
        renderBasket();
        const add = byId("shop-stock").querySelector(".shop-add");
        if (add) add.focus();
    });
}
