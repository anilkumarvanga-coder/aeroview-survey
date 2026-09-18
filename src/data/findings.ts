import {Finding} from '../models';
export const findingTypes=['Hotspot','Cracked Panel','Soiling','Shading','Vegetation','Damaged Module','Loose Connection','Structural Issue'];
export function makeFinding(projectId:string,index:number):Finding{return {id:`F-${1001+index}`,projectId,assetId:`PANEL-${1001+index%320}`,type:findingTypes[index%8],severity:['High','Medium','Low','Medium','Low','Critical','High','Medium'][index%8],confidence:87+index%13,date:['2026-09-18','2026-09-15','2026-09-10'][index%3],status:index%7===0?'Resolved':index%4===0?'In review':'Open',image:'/inspection-demo.png'}}
