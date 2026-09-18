'use client';
import {useState} from 'react';
import {User} from '../models';
import {projectService} from '../services/projectService';
import {authService} from '../services/authService';
import {droneService} from '../services/droneService';
import {roleLabel,permissions} from '../permissions';
import DataTable from '../components/DataTable';
import {Badge} from '../components/controls';
export default function Administration({user,view}:{user:User;view:string}){const [page,setPage]=useState(1);if(view==='clients'&&permissions(user).clients){const rows=projectService.clients(user);return <DataTable items={rows} total={rows.length} page={1} setPage={()=>{}} rowKey={r=>r.id} columns={[{label:'Client',render:r=>r.name},{label:'ID',render:r=>r.id},{label:'Contact',render:r=>r.contact},{label:'Projects',render:r=>projectService.list(user).filter(p=>p.clientId===r.id).length}]}/>}if(view==='users'&&permissions(user).users){const rows=authService.list();return <DataTable items={rows.slice((page-1)*10,page*10)} total={rows.length} page={page} setPage={setPage} rowKey={r=>r.id} columns={[{label:'Team member',render:r=>r.name},{label:'Email',render:r=>r.email},{label:'Access',render:r=>roleLabel(r)},{label:'Assignments',render:r=>r.projectIds.join(', ')||'All projects'}]}/>}if(view==='drones'&&permissions(user).drones){const rows=droneService.list(user);return <DataTable items={rows} total={rows.length} page={1} setPage={()=>{}} rowKey={r=>r.id} columns={[{label:'Drone ID',render:r=>r.id},{label:'Aircraft',render:r=>r.name},{label:'Status',render:r=><Badge>{r.status}</Badge>},{label:'Battery',render:r=>r.battery+'%'},{label:'Project',render:r=>r.projectId},{label:'Sensor',render:r=>r.sensor}]}/>}return <div className="empty">This page is not available for your role.</div>}
