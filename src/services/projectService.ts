import {projects} from '../data/projects';
import {clients} from '../data/clients';
import {hasProject,permissions} from '../permissions';
import {User,Project,Status} from '../models';
export const projectTypes={solar:{label:'Solar Survey',module:'solar'},transmission:{label:'Transmission Survey',module:'planned'},bridge:{label:'Bridge Inspection',module:'planned'},land:{label:'Land Survey',module:'planned'},infrastructure:{label:'Infrastructure Survey',module:'planned'},pole:{label:'Electrical Pole Inspection',module:'planned'},chimney:{label:'Chimney Inspection',module:'planned'},combined:{label:'Combined Project',module:'planned'}};
export const projectService={list:(u:User)=>projects.filter(p=>hasProject(u,p)),get:(u:User,id:string)=>projects.find(p=>p.id===id&&hasProject(u,p)),client:(id:string)=>clients.find(c=>c.id===id)?.name??'',clients:(u:User)=>permissions(u).clients?clients:[],setStatus:(u:User,id:string,status:Status):Project=>{if(!permissions(u).manage)throw Error('You cannot manage projects.');const p=projectService.get(u,id);if(!p)throw Error('Project unavailable.');p.status=status;return p;}};
