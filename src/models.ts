export type Role = 'super_admin'|'admin'|'manager'|'site_incharge'|'employee';
export type ProjectType = 'solar'|'transmission'|'land'|'bridge'|'infrastructure'|'pole'|'chimney'|'combined';
export type Status = 'Active'|'Completed'|'On Hold';
export interface User {id:string;name:string;email:string;loginType:'client'|'firm';role?:Role;clientId?:string;projectIds:string[]}
export interface Project {id:string;name:string;clientId:string;projectType:ProjectType;location:string;status:Status;area:number;panels:number;inspected:number;openFindings:number;lat:number;lng:number}
export interface Asset {id:string;projectId:string;type:string;location:string;condition:string;date:string;findings:number}
export interface FindingEvent {at:string;actor:string;action:string;remarks:string}
export interface Finding {id:string;projectId:string;assetId:string;type:string;severity:string;confidence:number;date:string;status:string;image:string;block:string;row:number;time:string;flightId:string;description:string;recommendation:string;remarks:string;assignee:string;risk:number;latitude:number;longitude:number;history:FindingEvent[]}
export interface FindingQuery extends Query {category?:string;block?:string;status?:string;risk?:number;start?:string;end?:string;sort?:string}
export interface Footage {id:string;projectId:string;title:string;block:string;date:string;time:string;flightId:string;drone:string;duration:string;source:string;poster:string;label:string}
export interface Flight {id:string;projectId:string;date:string;status:string;distance:number;duration:number;panels:number;findings:number;battery:number;droneId:string}
export interface Query {search?:string;filter?:string;page?:number;size?:number}
export interface Page<T> {items:T[];total:number}
