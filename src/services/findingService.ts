import {Finding,FindingQuery,User} from '../models';
import {projectService} from './projectService';
import {paginate} from './query';
import {canReviewFindings} from '../permissions';
const overrides=new Map<string,Finding>();
export const findingStatuses=['Open','In review','Resolved','Snoozed','Archived'];
export const riskLabels=['Very low','Low','Medium','High','Very high'];
async function records(u:User,projectId?:string):Promise<Finding[]> {
  const {makeFinding}=await import('../data/findings');
  return projectService.list(u).filter(p=>p.projectType==='solar'&&(!projectId||p.id===projectId)).flatMap(p=>Array.from({length:p.id==='SOL-001'?147:60},(_,i)=>{
    const f=makeFinding(p.id,i);
    return overrides.get(p.id+f.id)??{...f,latitude:p.lat+(i%6)*.0008,longitude:p.lng+(i%24)*.0002,status:p.status==='Completed'?'Resolved':f.status};
  }));
}
export const findingService={
  async list(u:User,projectId:string|undefined,q:FindingQuery={}) {
    const all=(await records(u,projectId)).filter(f=>
      (!q.search||[f.id,f.type,f.assetId,f.description,f.block,f.flightId].join(' ').toLowerCase().includes(q.search.toLowerCase()))&&
      (!q.filter||q.filter==='All severities'||f.severity===q.filter)&&
      (!q.risk||f.risk===q.risk)&&(!q.category||f.type===q.category)&&(!q.block||f.block===q.block)&&(!q.status||f.status===q.status)&&
      (!q.start||f.date>=q.start)&&(!q.end||f.date<=q.end));
    all.sort((a,b)=>q.sort==='oldest'?(a.date+a.time).localeCompare(b.date+b.time):q.sort==='risk'?b.risk-a.risk:(b.date+b.time).localeCompare(a.date+a.time));
    return {...paginate(all,q),counts:{open:all.filter(f=>f.status==='Open').length,review:all.filter(f=>f.status==='In review').length,resolved:all.filter(f=>f.status==='Resolved').length}};
  },
  async get(u:User,projectId:string,id:string){const f=(await records(u,projectId)).find(f=>f.id===id);if(!f)throw Error('Observation unavailable for this project.');return f;},
  async review(u:User,projectId:string,id:string,changes:{status:string;remarks:string;risk:number;assignee:string}) {
    if(!canReviewFindings(u)||!projectService.get(u,projectId))throw Error('Only assigned firm users can review observations.');
    if(!findingStatuses.includes(changes.status)||!Number.isInteger(changes.risk)||changes.risk<1||changes.risk>5)throw Error('Choose a valid status and risk rating.');
    if(changes.remarks.length>2000||changes.assignee.length>100)throw Error('Please shorten the remarks or assignee name.');
    const previous=await findingService.get(u,projectId,id);
    const action=[previous.status!==changes.status?`Status: ${previous.status} → ${changes.status}`:'',previous.risk!==changes.risk?`Risk: ${riskLabels[previous.risk-1]} → ${riskLabels[changes.risk-1]}`:'',previous.assignee!==changes.assignee?'Assignee updated':''].filter(Boolean).join(' · ')||'Review saved';
    const updated={...previous,...changes,history:[...previous.history,{at:new Date().toISOString(),actor:u.name,action,remarks:changes.remarks}]};
    overrides.set(projectId+id,updated);return updated;
  },
  async update(u:User,projectId:string,id:string,status:string){const f=await findingService.get(u,projectId,id);return findingService.review(u,projectId,id,{status,remarks:f.remarks,risk:f.risk,assignee:f.assignee});}
};
