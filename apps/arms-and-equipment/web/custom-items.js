"use strict";

const customItemTypes = {
    weapon: "weapon", ammunition: "ammunition", armor: "armor", shield: "shield",
    potion: "potion", ring: "ring", rod: "staff", scroll: "scroll", staff: "staff", wand: "staff"
};
let customItemId = "";
let editingCustomItem = false;

function readCustomItems() {
    return JSON.parse(Armory.customMagicItems()).sort((first, second) =>
        first.name.localeCompare(second.name) || first.id.localeCompare(second.id));
}

function renderCustomItems() {
    const items = readCustomItems();
    const list = byId("custom-items-list");
    list.textContent = "";
    byId("custom-items-empty").hidden = items.length !== 0;
    items.forEach(item => {
        const card = element("button", "", "card");
        card.type = "button";
        card.dataset.customItemId = item.id;
        card.dataset.rarity = item.rarity;
        card.setAttribute("aria-pressed", String(item.id === customItemId));
        card.appendChild(icon("images/types/" + (customItemTypes[item.type] || "gear") + ".svg"));
        card.appendChild(element("strong", item.name));
        card.appendChild(element("small", [pretty(item.type), pretty(item.rarity)].join(" · ")));
        card.addEventListener("click", () => showCustomItem(item));
        list.appendChild(card);
    });
}

function showCustomItem(item, status = "") {
    customItemId = item ? item.id : "";
    editingCustomItem = false;
    byId("custom-item-form").hidden = true;
    const panel = byId("custom-item-panel");
    const detail = byId("custom-item-details");
    detail.hidden = !item;
    panel.hidden = !item && !status;
    byId("custom-item-status").textContent = status;
    detail.textContent = "";
    renderCustomItems();
    if (!item) {
        byId("custom-item-new").focus();
        return;
    }

    const heading = element("h3", item.name);
    heading.tabIndex = -1;
    detail.appendChild(heading);
    const stats = [["Type", pretty(item.type)], ["Rarity", pretty(item.rarity)], ["Attunement", item.attunement],
        ["Value", item.price ? item.price + " gp" : ""]];
    if (item.type === "weapon" || item.type === "ammunition") {
        stats.push(["Damage", item.damage], ["Range or reach", item.range], ["Properties and mastery", item.properties]);
    }
    if (item.type === "armor" || item.type === "shield") stats.push(["Armor Class", item.ac]);
    statList(detail, stats);
    [["Rules and effects", item.rules], ["Notes", item.notes]].forEach(([label, value]) => {
        if (!value) return;
        detail.appendChild(element("h4", label));
        detail.appendChild(element("p", value, "detail-description"));
    });

    const actions = element("div", "", "actions");
    const edit = element("button", "Edit");
    edit.id = "custom-item-edit";
    edit.addEventListener("click", () => editCustomItem(item));
    actions.appendChild(edit);
    const exportText = () => [item.name, ...stats.filter(([, value]) => value).map(([label, value]) => label + " — " + value),
        item.rules, item.notes ? "Notes\n" + item.notes : ""].filter(Boolean).join("\n\n");
    const copy = element("button", "Copy entry");
    copy.addEventListener("click", () => {
        byId("custom-item-status").textContent = Armory.copyEntry(item.name, exportText()) ? "Copied." : "Could not copy the item.";
    });
    actions.appendChild(copy);
    const pdf = element("button", "Share PDF");
    pdf.addEventListener("click", () => {
        byId("custom-item-status").textContent = Armory.sharePdf(item.name, exportText());
    });
    actions.appendChild(pdf);

    const remove = element("button", "Delete");
    remove.id = "custom-item-delete";
    actions.appendChild(remove);
    const confirm = element("button", "Delete item permanently");
    confirm.id = "custom-item-confirm-delete";
    const cancel = element("button", "Keep item");
    const confirmation = element("div", "", "actions");
    confirmation.hidden = true;
    confirmation.appendChild(confirm);
    confirmation.appendChild(cancel);
    remove.addEventListener("click", () => {
        confirmation.hidden = false;
        confirm.focus();
    });
    cancel.addEventListener("click", () => {
        confirmation.hidden = true;
        remove.focus();
    });
    confirm.addEventListener("click", () => {
        if (Armory.deleteCustomMagicItem(item.id)) showCustomItem(null, "Item deleted.");
        else byId("custom-item-status").textContent = "Could not delete the item.";
    });
    detail.appendChild(actions);
    detail.appendChild(confirmation);
    heading.focus();
}

function syncCustomItemFields() {
    const type = byId("custom-item-type").value;
    const weapon = byId("custom-item-weapon-fields");
    const armor = byId("custom-item-armor-fields");
    weapon.disabled = weapon.hidden = type !== "weapon" && type !== "ammunition";
    armor.disabled = armor.hidden = type !== "armor" && type !== "shield";
}

function editCustomItem(item) {
    editingCustomItem = true;
    customItemId = item ? item.id : "";
    const form = byId("custom-item-form");
    form.reset();
    if (item) Object.keys(item).forEach(key => {
        if (form.elements.namedItem(key)) form.elements.namedItem(key).value = item[key];
    });
    syncCustomItemFields();
    byId("custom-item-form-heading").textContent = item ? "Edit magic item" : "Create magic item";
    byId("custom-item-details").hidden = true;
    byId("custom-item-status").textContent = "";
    byId("custom-item-panel").hidden = false;
    form.hidden = false;
    renderCustomItems();
    byId("custom-item-name").focus();
}

function closeCustomItems() {
    if (byId("custom-items").hidden) return false;
    if (editingCustomItem) {
        showCustomItem(readCustomItems().find(item => item.id === customItemId));
        return true;
    }
    byId("custom-items").hidden = true;
    document.querySelector("main > .shelf").hidden = false;
    inspection.hidden = false;
    byId("about").hidden = false;
    byId("open-custom-items").focus();
    return true;
}

byId("open-custom-items").addEventListener("click", () => {
    dismissInspection(false);
    document.querySelector("main > .shelf").hidden = true;
    inspection.hidden = true;
    byId("about").hidden = true;
    byId("custom-items").hidden = false;
    showCustomItem(null);
});
byId("close-custom-items").addEventListener("click", () => {
    editingCustomItem = false;
    closeCustomItems();
});
byId("custom-item-new").addEventListener("click", () => editCustomItem(null));
byId("custom-item-type").addEventListener("change", syncCustomItemFields);
byId("custom-item-cancel").addEventListener("click", () =>
    showCustomItem(readCustomItems().find(item => item.id === customItemId)));
byId("custom-item-form").addEventListener("submit", event => {
    event.preventDefault();
    const item = {id: customItemId};
    new FormData(event.currentTarget).forEach((value, key) => { item[key] = value.trim(); });
    if (!item.name) {
        byId("custom-item-status").textContent = "Enter an item name.";
        byId("custom-item-name").focus();
        return;
    }
    if (item.price) item.price = String(Number(item.price));
    const saved = Armory.saveCustomMagicItem(JSON.stringify(item));
    if (saved) showCustomItem(readCustomItems().find(row => row.id === saved), "Item saved.");
    else byId("custom-item-status").textContent = "Could not save the item. Check the name and value.";
});
