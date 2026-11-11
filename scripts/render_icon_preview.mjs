import fs from 'node:fs/promises';
import path from 'node:path';
import sharp from '/home/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp/dist/index.mjs';
const root=path.resolve(import.meta.dirname,'..');
const names=['dagger','sword','axe','hammer','bow','crossbow','light-armor','medium-armor','heavy-armor','shield','helmet','gloves','potion','scroll','ring','amulet','staff','tools'];
let body='<rect width="1080" height="640" fill="#15181e"/><text x="28" y="42" fill="#d2b077" font-family="serif" font-size="27">Shared equipment icons</text><text x="28" y="69" fill="#d1ccc1" font-family="sans-serif" font-size="14">Generic type artwork • item-specific illustrations can replace these later</text>';
for(let i=0;i<names.length;i++){
 const x=28+(i%6)*174,y=90+Math.floor(i/6)*160;
 const svg=await fs.readFile(path.join(root,'catalog/images/types',names[i]+'.svg'),'utf8');
 body+=`<rect x="${x}" y="${y}" width="154" height="145" rx="8" fill="#22232a" stroke="#806b47"/><image x="${x+33}" y="${y+12}" width="88" height="88" href="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}"/><text x="${x+77}" y="${y+127}" text-anchor="middle" fill="#e2d5bd" font-family="sans-serif" font-size="14">${names[i].replaceAll('-',' ')}</text>`;
}
body+='<text x="28" y="605" fill="#b5ada0" font-family="sans-serif" font-size="12">Icons by Game-icons.net contributors • CC BY 3.0 • per-file credits in catalog/images/manifest.json</text>';
const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="640">${body}</svg>`;
await sharp(Buffer.from(svg)).png().toFile(path.join(root,'catalog/images/type-preview.png'));
