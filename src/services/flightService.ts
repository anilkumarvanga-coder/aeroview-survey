import {User,Query} from '../models';
import {projectService} from './projectService';
import {paginate} from './query';
export const flightService={async list(u:User,projectId?:string,q:Query={}){const {makeFlight}=await import('../data/flights');const records=projectService.list(u).filter(p=>p.projectType==='solar'&&(!projectId||p.id===projectId)).flatMap(p=>Array.from({length:8},(_,i)=>makeFlight(p.id,i))).filter(f=>(!q.search||(f.id+f.date+f.droneId).toLowerCase().includes(q.search.toLowerCase()))&&(!q.filter||q.filter==='All dates'||f.date===q.filter));return paginate(records,q)}};
