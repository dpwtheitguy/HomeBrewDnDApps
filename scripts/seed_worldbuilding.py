#!/usr/bin/env python3
"""Original construction proposals; sources establish systems, not canonical prices."""
import json,re
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'catalog/settings/worldbuilding';folder.mkdir(parents=True,exist_ok=True)
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False))
refs=[{'id':'bastions','url':'https://www.dndbeyond.com/posts/1828-exploring-bastions-from-the-2024-dungeon-masters','label':'2024 DMG Bastions overview','source_kind':'official-public-overview','note':'Establishes the system, not the mechanics or prices of the original project structures below.'},
 {'id':'stronghold-3e','url':'https://en.wikipedia.org/wiki/Stronghold_Builder%27s_Guidebook','label':'Stronghold Builder’s Guidebook (2002, D&D 3.0)','source_kind':'bibliography','note':'Component/building research queued. Project costs are not extracted book costs.'},
 {'id':'castle-2e','url':'https://www.tsrarchive.com/add/add-dmgr.html','label':'The Castle Guide (DMGR2, AD&D 2e)','source_kind':'bibliography'},
 {'id':'hero-3e','url':'https://www.tsrarchive.com/3e/3e2-pa.html','label':'Hero Builder’s Guidebook (D&D 3.0)','source_kind':'bibliography','note':'Character-building source; equipment audit pending. Not confused with Stronghold Builder’s Guidebook.'},
 {'id':'stronghold-game','url':'https://store.steampowered.com/app/40970/Stronghold_Crusader_HD/','label':'Stronghold Crusader','source_kind':'official-game-product-page','note':'Construction/economy inspiration only, not a verified item list.'},
 {'id':'valheim','url':'https://valheim.gaming.tools/structures/','label':'Valheim public building index','source_kind':'fan-structure-index'},
 {'id':'cyclopedia','url':'https://en.wikipedia.org/wiki/Dungeons_%26_Dragons_Rules_Cyclopedia','label':'Rules Cyclopedia dominion/stronghold research','source_kind':'bibliography','note':'Legacy construction and dominion rules queued, not imported as current RAW.'}]
entities=[]
def entity(kind,key,label,aliases=()):entities.append({'id':kind+':'+key,'kind':kind,'label':label,'aliases':list(aliases),'parent_ids':[],'note':'Research facet; not a claim that original source mechanics are implemented.'})
entity('topic','worldbuilding','Worldbuilding construction',('construction','building','fortifications','settlement building'))
for key,label,aliases in [('bastions-2024','Bastions (2024 DMG)',('bastions',)),('stronghold-builder-3e','Stronghold Builder’s Guidebook',('Stronghold Builders Guidebook',)),('castle-guide-2e','The Castle Guide',('DMGR2',)),('hero-builder-3e','Hero Builder’s Guidebook',('Hero Builders Guidebook',))]:entity('publication',key,label,aliases)
entity('game','valheim','Valheim');entity('game','stronghold-crusader','Stronghold Crusader')
# Explicit authored proposals, not procedurally multiplied source variants.
rows=[
 ('Bedroll Camp','camp',10,10,5,10,1,1,4,'canvas, rope, bedding','Packable shelter for four; no comfort magic or guard service.'),
 ('Field Kitchen','camp',10,10,8,75,2,2,8,'timber, iron stove, cookware','Cooking station; food, fuel and a cook are separate.'),
 ('Covered Supply Cache','camp',10,10,6,50,2,1,0,'timber, canvas, lock fittings','Dry storage for 500 pounds; no automatic concealment or theft immunity.'),
 ('Water Collection Station','camp',10,10,8,100,2,3,0,'gutters, barrels, cloth filters','Rain collection; output depends on weather and does not purify poison or disease.'),
 ('Camp Latrine','camp',5,10,6,25,2,1,0,'timber, tools, screening','A sanitation fixture; placement and groundwater conditions need DM review.'),
 ('Camp Watch Platform','camp',10,10,15,150,3,4,2,'timber, rope, ladder','A lookout position; seeing farther depends on terrain and normal sight rules.'),
 ('Horse Picket Line','camp',20,10,4,30,2,1,6,'posts, rope, tack hooks','Holds up to six ordinary mounts; grants no food, water or automatic animal handling.'),
 ('Timber Palisade Section','fort',10,2,10,100,3,3,0,'timber, iron fasteners','One ten-foot boundary segment. No closed perimeter unless connected to other segments.'),
 ('Timber Gate','fort',10,3,10,150,3,4,0,'timber, hinges, locking bar','A ten-foot gate for a palisade; a guard must operate its bar.'),
 ('Earthen Rampart Section','fort',10,10,5,75,4,3,0,'earth, retaining timber','One short rampart segment. Drainage and soil stability are site dependent.'),
 ('Stone Curtain Wall Section','castle',10,5,15,750,6,10,0,'dressed stone, mortar, timber scaffold','One ten-foot wall segment, with a narrow parapet. No enclosed castle is implied.'),
 ('Stone Watchtower','castle',15,15,30,5000,8,40,6,'stone, mortar, timber stairs','A three-level watch post with capacity for six occupants, not six permanent hirelings.'),
 ('Gatehouse','castle',20,20,25,7500,10,45,8,'stone, timber, hinges, portcullis','A guarded entrance; locks and staff do not confer automatic detection of intruders.'),
 ('Drawbridge','castle',15,10,5,1500,5,15,0,'timber deck, chains, winch','Spans one ten-foot gap. Raising or lowering requires an operator and an action in an encounter.'),
 ('Dry Moat Section','fort',10,10,10,100,4,4,0,'excavated earth, shoring','One ten-foot trench section. It does not automatically fill with water or damage creatures.'),
 ('Guard Barracks','fort',20,30,10,1500,6,20,12,'timber, roof tiles, bunks','Beds for twelve. Guards, their equipment and wages must be recruited and budgeted separately.'),
 ('Training Yard','fort',30,30,0,300,4,5,12,'packed earth, target frames, rails','Practice space for twelve; no automatic XP, feat, proficiency or combat bonus.'),
 ('Armory Storehouse','fort',15,20,10,1000,5,15,0,'timber, iron racks, locks','Equipment storage; weapons and armor are not included in its construction price.'),
 ('Masonry Workshop','village',20,20,12,1000,5,15,4,'stone benches, shelter, hand tools','Work area for four artisans; no automatic crafting output or proficiency.'),
 ('Smithy','village',20,20,15,2000,6,20,3,'stone hearth, bellows, anvil','A workshop, not a source of free finished weapons; requires staff, fuel and stock.'),
 ('Carpenter’s Workshop','village',20,20,12,750,4,12,4,'timber, benches, saw fixtures','Four workspaces; work follows ordinary tools, proficiency and crafting rules.'),
 ('Weaving House','village',15,20,10,500,4,10,4,'timber, loom frames, benches','Space for four weavers; cloth inputs and paid labor remain separate.'),
 ('Potter’s Kiln House','village',15,20,12,700,4,12,3,'clay bricks, kiln, timber shelter','Three workspaces; drying time, firing fuel and finished goods are not free.'),
 ('Granary','village',20,20,15,1000,5,15,0,'timber, raised floor, sealed bins','Dry storage for 10,000 pounds of grain. Spoilage and pests remain campaign concerns.'),
 ('Public Well','village',10,10,5,750,5,15,0,'stone lining, timber winch, rope','Water access is contingent on a suitable aquifer. No guaranteed drilling success or purification.'),
 ('Village Longhouse','village',20,40,15,1800,6,25,20,'timber, roof materials, hearth stone','Shared indoor space for twenty; food, bedding and residents are not included.'),
 ('Market Stall','village',10,10,10,100,2,3,2,'timber, canvas, display counter','Two-person trading workspace; no guaranteed income or merchant availability.'),
 ('Village Storehouse','village',20,20,12,750,4,12,0,'timber, shelving, lock fittings','Stores ordinary goods up to 5,000 pounds; security depends on locks and staff.'),
 ('Infirmary','village',20,20,10,1500,5,18,8,'timber, washable surfaces, beds','Eight patient beds. Healers, medicines, spells and cure outcomes are not included.'),
 ('Village Meeting Hall','village',30,40,15,3000,8,30,40,'timber, stone footings, benches','Assembly space for forty; grants no legal authority, loyalty bonus or automatic peace.'),
 ('Town Sewer Section','city',10,10,10,1000,6,15,0,'masonry, shoring, drainage channel','One ten-foot tunnel segment; sewage outflow and disease prevention require a coherent plan.'),
 ('Stone Bridge','city',15,30,15,6000,10,45,0,'stone, mortar, scaffold','A thirty-foot pedestrian/cart span on sound foundations. Water flow and loads need site review.'),
 ('Dock Section','city',10,20,5,800,4,12,0,'piles, timber decking, mooring rings','Twenty-foot access platform; water depth and vessel clearance remain location dependent.'),
 ('Town Library','city',20,30,15,2500,6,25,12,'timber, shelving, dry storage','Twelve reader seats and shelving. Books, lore access and research success are not included.'),
 ('City Archive','city',20,20,12,2000,5,20,4,'masonry, shelves, document cabinets','Four workspaces; the owner supplies records. No automatic truth detection or secret knowledge.'),
 ('Public Bathhouse','city',20,30,12,3000,6,30,12,'masonry, piping, hearth, basins','Twelve bathing places. Fresh water, fuel, attendants and sanitary operation cost extra.'),
 ('Townhouse','city',20,30,20,3000,6,30,8,'masonry, timber floors, roof tiles','Two-floor residence for eight; land, taxes and title are separate.'),
 ('Signal Beacon','city',10,10,20,500,3,8,2,'stone base, fuel basket, timber ladder','Visible fire signal depends on elevation and weather. Fuel and agreed codes are separate.'),
 ('Dungeon Corridor Section','dungeon',10,10,10,750,5,12,0,'cut stone, supports, floor slabs','One ten-foot passage section. Excavation beyond the footprint and geological hazards cost extra.'),
 ('Dungeon Chamber','dungeon',20,20,10,2000,6,25,8,'cut stone, supports, door frame','A twenty-foot chamber; no monsters, traps, treasure or secret exits included.'),
 ('Reinforced Dungeon Door','dungeon',5,1,8,250,2,3,0,'timber, iron bands, hinges','An installed door; lock quality, sound transmission and breaking DC are DM adjudications.'),
 ('Secret Door Assembly','dungeon',5,2,8,1000,4,10,0,'fitted masonry, pivots, concealed latch','A concealed doorway; discovery requires normal search adjudication, not universal invisibility.'),
 ('Dungeon Cistern','dungeon',10,10,10,1000,5,15,0,'sealed masonry, drain fittings','Holds up to 5,000 gallons if sound and supplied. Water and purification are not included.'),
 ('Dungeon Ventilation Shaft','dungeon',5,5,20,750,4,12,0,'cut stone, timber shoring, grate','A twenty-foot air shaft; airflow is not assured without site review. No immunity to smoke or gas.'),
 ('Secure Holding Cell','dungeon',10,10,10,750,4,10,1,'masonry, iron bars, lock fittings','A single-occupant room; escape DC, safety and lawful use are campaign adjudications.'),
 ('Underground Storeroom','dungeon',15,20,10,1500,5,20,0,'masonry, shelving, moisture barriers','Storage for 3,000 pounds. Flooding, moisture and access must be considered.'),
 ('Excavation Staging Area','dungeon',20,20,10,300,4,5,6,'shoring timber, tool racks, wheelbarrows','Six-worker preparation area; it does not make excavation safe or instantly complete.'),
 ('Surveyor’s Map Room','castle',15,20,10,750,4,12,6,'timber, tables, map cabinets','Six-person planning room. Maps, surveyed distances and regional knowledge are separate inputs.')]
items=[]
for name,scope,w,l,h,cost,workers,days,capacity,materials,benefit in rows:
 iid='construction:'+re.sub(r'[^a-z0-9]+','-',name.casefold()).strip('-')
 details=f'Original 2024 campaign proposal. {benefit} Estimated footprint: {w} by {l} feet; height {h} feet. Estimated construction: {workers} workers for {days} days in ordinary conditions. Price includes ordinary materials and construction labor; excludes land, permissions, extraordinary site preparation, furnishings not named, ongoing staffing, supplies and taxes. The DM confirms costs and site suitability. This grants no official Bastion orders, special-facility benefits or class features.'
 structure={'schema_version':1,'kind':'facility' if scope not in ['fort','castle','dungeon'] else 'fortification' if scope in ['fort','castle'] else 'dungeon-component','scale':scope,'footprint':{'width_ft':w,'length_ft':l,'height_ft':h},'construction':{'cost_gp':str(cost),'workers':workers,'days':days,'materials_summary':materials,'cost_includes':['ordinary-materials','construction-labor'],'cost_excludes':['land','permits','extraordinary-site-work','ongoing-staff','operating-supplies','taxes'],'estimate_status':'project-house-rule-not-RAW'},'capacity':{'occupants':capacity,'status':'design-estimate'},'maintenance':{'gp_per_30_days':str(max(1,cost//100)),'status':'author-estimate-excludes-staff-and-supplies'},'defenses':{'armor_class':None,'hit_points':None,'damage_threshold':None,'status':'DM-object-and-siege-rules-required'},'placement':{'requires_site_review':True,'connection_rules_implemented':False},'automation_status':'data-only-not-a-building-simulator'}
 items.append({'id':iid,'name':name,'type':'structure','icon':'gear','mode':'original-construction-proposal','magic':False,'record_kind':'structure','evidence_ref':'bastions','entity_id':'publication:bastions-2024','estimated_value_gp':cost,'tldr':benefit,'details':details,'changes':'Independent system-compatible construction concept. No sourcebook cost table or official special-facility effect has been ported.','flavor':'Its character will come from the people who build and maintain it.','creative':'Combine it with complementary facilities in a site plan; shared walls, utility connections and bulk discounts require a DM-approved budget.','structure':structure,'tags':['construction-scale:'+scope,'construction-status:proposal']})
pack={'schema_version':1,'id':'worldbuilding-2024-drafts','label':'Worldbuilding construction proposals (2024 house rules)','theme':'worldbuilding','topic_entity_id':'topic:worldbuilding','coverage':'48 original camp, fort, castle, village, city and dungeon proposals; not official Bastion special facilities or a complete stronghold-book import.','sources':refs,'entities':entities,'items':items,'filter_profiles':[{'id':'worldbuilding-workbench','label':'Worldbuilding workbench','filters':{'tags':['theme:worldbuilding']},'note':'Original structures and explicitly unconverted construction references.'}]}
save(folder/'research-pack.json',pack)
save(folder/'research-queue.json',{'workstreams':[{'id':k,'label':l,'status':status,'original_book_item_audit_complete':False} for k,l,status in [('hero-builder-3e','Hero Builder’s Guidebook','bibliography-verified-equipment-audit-pending'),('stronghold-builder-3e','Stronghold Builder’s Guidebook','bibliography-verified-component-audit-pending'),('castle-guide-2e','The Castle Guide','bibliography-verified-construction-audit-pending'),('bastions-2024','2024 DMG Bastions','official-overview-checked-original-proposals-only'),('construction-video-games','Valheim / Stronghold / Dungeon Keeper / Dwarf Fortress','selected-reference-imports-more-games-pending')]]})
print('Construction proposals',len(items))
