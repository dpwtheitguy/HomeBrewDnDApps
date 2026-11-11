#!/usr/bin/env python3
"""Editorial vocabulary and scope roadmap; entries are not claims of imported content."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
def save(path,data):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))
entities=[]
def entity(kind,key,label,aliases=(),parents=(),**extra):
 entities.append({'id':kind+':'+key,'kind':kind,'label':label,'aliases':list(aliases),'parent_ids':list(parents),**extra})
for key,label,aliases in [('mystara','Mystara',()),('forgotten-realms','Forgotten Realms',('Faerun','Faerûn')),('planescape','Planescape',('Platescape',)),('ravenloft','Ravenloft',()),('greyhawk','Greyhawk',('World of Greyhawk',)),('sanctuary','Sanctuary',('Diablo setting',))]:entity('setting',key,label,aliases)
entity('publication','mystara-gaz5','The Elves of Alfheim',('GAZ5',),('setting:mystara',))
entity('region','known-world','Known World',('The Known World',),('setting:mystara',))
regions=[('karameikos','Karameikos'),('glantri','Glantri'),('ylaruam','Ylaruam'),('ierendi','Ierendi'),('alfheim','Alfheim'),('rockhome','Rockhome'),('northern-reaches','Northern Reaches'),('five-shires','Five Shires'),('minrothad','Minrothad'),('broken-lands','Broken Lands'),('darokin','Darokin'),('ethengar','Ethengar'),('shadow-elves','Shadow Elf Territories'),('atruaghin','Atruaghin Clans'),('thyatis','Thyatis'),('alphatia','Alphatia')]
for key,label in regions:entity('region',key,label,parents=('region:known-world',))
for key,label,parent in [('hollow-world','Hollow World','setting:mystara'),('savage-coast','Savage Coast','setting:mystara'),('nithia','Nithia','region:hollow-world'),('milenian-empire','Milenian Empire','region:hollow-world'),('bellayne','Bellayne','region:savage-coast'),('thay','Thay','setting:forgotten-realms'),('barovia','Barovia','setting:ravenloft'),('sigil','Sigil','setting:planescape')]:entity('region',key,label,parents=(parent,))
for key,label in [('bear','Children of the Bear'),('turtle','Children of the Turtle'),('horse','Children of the Horse'),('elk','Children of the Elk'),('tiger','Children of the Tiger')]:entity('region','atruaghin-'+key,label,parents=('region:atruaghin',))
for key,label,parent in [('cayma','Cayma communities','region:savage-coast'),('gurrash','Gurrash communities','region:savage-coast'),('ee-aar',"Ee’aar communities",'region:savage-coast'),('wallara','Wallara communities','region:savage-coast'),('sea-people','Sea People','setting:mystara'),('rakasta','Rakasta communities','setting:mystara')]:entity('region',key,label,parents=(parent,),note='Regional/community association vocabulary; not an ethnic proficiency rule.')
for key,label,aliases in [('karameikan','Karameikan',('Karameikan regional style',)),('traladaran','Traladaran',('Traladar',)),('thyatian','Thyatian',()),('glantrian','Glantrian',()),('thayan','Thayan',())]:entity('culture',key,label,aliases,note='Cultural or regional style. Do not infer character ancestry, alignment, proficiency or item ownership from this tag.')
entity('faction','red-wizards-of-thay','Red Wizards of Thay',('Red Wizards',),note='Faction association is distinct from Thayan culture.')
for key,label in [('baldurs-gate-1',"Baldur’s Gate I"),('baldurs-gate-2',"Baldur’s Gate II"),('baldurs-gate-3',"Baldur’s Gate 3"),('diablo-1','Diablo I'),('diablo-2','Diablo II'),('diablo-3','Diablo III'),('diablo-4','Diablo IV')]:entity('game',key,label)
save('catalog/taxonomy/entities.json',{'schema_version':1,'entities':entities,'relationship_roles':['setting','cultural-association','origin','available-in','used-by','found-in','inspired-by'],'unknown_policy':'An absent association means unknown, not universally available or forbidden.'})
profiles=[
 {'id':'all-research','label':'All research','filters':{},'default_for_cli':True,'note':'Shows metadata and unreviewed drafts with their status. No rule compatibility is implied.'},
 {'id':'tabletop-2024','label':'2024 tabletop references','filters':{'rulesets':['dnd-2024'],'exclude_content_statuses':['factual-metadata-only','original-conversion-draft']},'note':'Source transcriptions are still unverified; this profile is not a rules-audit certificate.'},
 {'id':'mystara-workbench','label':'Mystara conversion workbench','filters':{'settings':['mystara']},'note':'Includes current Mystara drafts. Other setting packs are not silently enabled.'},
 {'id':'bg3-reference','label':'BG3 references','filters':{'rulesets':['bg3']},'note':'Game data requiring tabletop conversion.'}
]
save('catalog/filters/presets.json',{'schema_version':1,'profiles':profiles,'matching':'OR within a facet; AND between facets; repeated --tag remains AND.','scope_precedence':['global-defaults','campaign-profile','character-overrides','current-search'],'persistence_status':'Profile file and CLI evaluation implemented. Android settings persistence and filter-chip UI are not implemented.'})
roadmap=[('mystara','Mystara / Known World / GAZ1–GAZ14 / boxed sets',1,'active-initial-import'),('karameikos-box','Karameikos: Kingdom of Adventure',1,'bibliography-and-internet-evidence'),('glantri-box','Glantri: Kingdom of Magic',1,'bibliography-and-internet-evidence'),('planescape','Planescape',2,'queued'),('ravenloft','Ravenloft',2,'queued'),('curse-of-strahd','Curse of Strahd',2,'queued'),('baldurs-gate-1',"Baldur’s Gate I",3,'queued'),('baldurs-gate-2',"Baldur’s Gate II",3,'queued'),('baldurs-gate-3',"Baldur’s Gate 3",3,'game-metadata-imported'),('forgotten-realms','Forgotten Realms',3,'partial-via-BG3-no-general-book-audit'),('return-temple','Return to the Temple of Elemental Evil',4,'queued-Greyhawk-3e'),('zanzer',"Zanzer’s Dungeon / Escape from Zanzer’s Dungeon",1,'identity-likely-needs-edition-confirmation'),('diablo-1','Diablo I',5,'queued'),('diablo-2','Diablo II',5,'queued'),('diablo-3','Diablo III',5,'queued'),('diablo-4','Diablo IV',5,'queued-version-pinning-required'),('arms-equipment-3e','Arms and Equipment Guide (3e)',4,'queued'),('arms-equipment-4e','4e equipment books, including Adventurer’s Vault series',4,'bibliography-to-verify'),('arms-equipment-5e','5e equipment guides and catalogs',4,'specific-titles-to-identify')]
save('catalog/source-roadmap.json',{'priority':'Mystara depth before breadth','sources':[{'id':a,'label':b,'priority':c,'status':d} for a,b,c,d in roadmap],'count_policy':'30,000 is a possible target, not a verified unique-item count. Families, reprints, conversions, rolled affixes, variants and instances must be counted separately.','working_assumptions':["Zanzar most likely refers to Zanzer. Do not merge different adventures until verified.",'Do not assume all requested editions have an identically titled Arms and Equipment Guide.','Return to the Temple of Elemental Evil is a Greyhawk adventure, not a Forgotten Realms source.','Diablo affixes, runewords and set bonuses need separate entities rather than arbitrary expanded item combinations.']})
print('Vocabulary entities:',len(entities),'saved profiles:',len(profiles),'roadmap entries:',len(roadmap))
if __name__=='__main__':pass

# Adventure research extensions survive a vocabulary reset.
from adventure_packs import merge_entities
merge_entities(ROOT)
