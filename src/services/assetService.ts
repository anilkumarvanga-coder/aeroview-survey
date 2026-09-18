import {Query,User} from '../models';
import {projectService} from './projectService';
import {paginate} from './query';
export const assetService={async list(u:User,projectId:string|undefined,q:Query={}){const {makeAsset}=await import('../data/assets');const ps=projectService.list(u).filter(p=>p.projectType==='solar'&&(!projectId||p.id===projectId));const records=ps.flatMap(p=>Array.from({length:320},(_,i)=>makeAsset(p.id,i))).filter(a=>(!q.search||(a.id+a.location+a.type).toLowerCase().includes(q.search.toLowerCase()))&&(!q.filter||q.filter==='All types'||a.type===q.filter));return paginate(records,q)}};
