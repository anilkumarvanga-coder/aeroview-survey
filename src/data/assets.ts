import {Asset} from '../models';
export const assetTypes=['Solar Panel','Inverter','Mounting Structure','Transformer','Combiner Box','Electrical Equipment'];
export function makeAsset(projectId:string,index:number):Asset{const type=assetTypes[index%16<11?0:(index%16)-10];return {id:`${type==='Solar Panel'?'PANEL':type.toUpperCase().replace(' ','-')}-${1001+index}`,projectId,type,location:`Block ${String.fromCharCode(65+index%6)} · Row ${index%24+1}`,condition:index%17===0?'Critical':index%5===0?'Attention Required':'Good',date:'2026-09-18',findings:index%17===0?3:index%5===0?2:0}}
