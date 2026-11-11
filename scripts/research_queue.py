#!/usr/bin/env python3
"""Inspect or record the research loop. Recording does not fetch or invent evidence.
--next --limit 4 emits queries. --record TASK --url URL --title TITLE records a lead.
"""
import argparse,json,collections,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/'catalog/research/queue.json'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--next',action='store_true');p.add_argument('--limit',type=int,default=4);p.add_argument('--entity');p.add_argument('--category');p.add_argument('--record');p.add_argument('--url');p.add_argument('--title');p.add_argument('--note');p.add_argument('--status',choices=['searched-no-evidence-yet','source-leads-found','source-inspected','conversion-draft','reviewed'],default='source-leads-found');a=p.parse_args()
 d=json.loads(PATH.read_text());tasks=d['tasks']
 if a.record:
  row=next((x for x in tasks if x['id']==a.record),None)
  if row is None:p.error('Unknown task')
  if a.status!='searched-no-evidence-yet' and not(a.url and a.title):p.error('A source URL and title are required')
  row['search_attempts']+=1;row['status']=a.status
  if a.url:row['evidence'].append({'url':a.url,'title':a.title,'note':a.note,'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 if a.next:
  selected=[t for t in tasks if t['status']=='unsearched' and (not a.entity or t['entity_id']==a.entity) and (not a.category or t['category']==a.category)][:a.limit]
  print(json.dumps(selected,ensure_ascii=False,indent=2))
 else:print(json.dumps({'tasks':len(tasks),'by_status':dict(collections.Counter(t['status'] for t in tasks))},indent=2))
if __name__=='__main__':main()
