import {User} from '../models';
import {projectService} from './projectService';
import {makeFootage} from '../data/footage';
export const mediaService={list:(u:User,projectId:string)=>projectService.get(u,projectId)?.projectType==='solar'?Array.from({length:6},(_,i)=>makeFootage(projectId,i)):[],live:(u:User,projectId:string)=>projectService.get(u,projectId)?.projectType==='solar'?makeFootage(projectId,0):undefined};
