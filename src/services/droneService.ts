import {drones} from '../data/drones';
import {User} from '../models';
import {projectService} from './projectService';
export const droneService={list:(u:User)=>drones.filter(d=>projectService.get(u,d.projectId))};
