import {Finding} from '../models';
export const findingTypes=['Hotspot','Cracked Panel','Soiling','Shading','Vegetation','Damaged Module','Loose Connection','Structural Issue'];
const descriptions=[
  'Localized thermal anomaly identified on a solar module. Confirm temperature difference during a field inspection.',
  'Possible surface fracture observed on the module. Inspect the glass and check electrical output.',
  'Uneven deposits are visible across the module surface, which may reduce light reaching the cells.',
  'An obstruction casts a shadow across part of the string during this inspection.',
  'Vegetation is approaching the panel edge and the maintenance access corridor.',
  'Visible module damage requires a closer inspection before planning repairs.',
  'A connection point was flagged for inspection. Confirm fastening and electrical continuity.',
  'A mounting assembly may be misaligned. Verify supports, fasteners, and module clearance.'
];
const recommendations=[
  'Verify the hotspot with a calibrated thermal inspection and electrical testing. Isolate or replace the affected module if confirmed by the site engineer.',
  'Have the maintenance team inspect the module and schedule replacement if the damage is confirmed.',
  'Schedule cleaning using the site-approved process, then compare output with adjacent modules.',
  'Identify and remove the source of shading where feasible. Compare a follow-up inspection at the same time of day.',
  'Schedule vegetation clearance around the affected row and maintain the approved access corridor.',
  'Arrange an on-site inspection and have the site engineer determine whether replacement is required.',
  'Arrange inspection by qualified electrical personnel and record the corrective action taken.',
  'Have the structures team verify alignment and fasteners, then capture follow-up evidence.'
];
export function makeFinding(projectId:string,index:number):Finding {
  const k=index%8, date=['2026-09-18','2026-09-15','2026-09-10'][index%3];
  const status=index%7===0?'Resolved':index%4===0?'In review':'Open';
  return {id:`F-${1001+index}`,projectId,assetId:`PANEL-${1001+index%320}`,type:findingTypes[k],severity:['High','Medium','Low','Medium','Low','Critical','High','Medium'][k],confidence:87+index%13,date,status,image:'/inspection-demo.png',block:`Block ${String.fromCharCode(65+index%6)}`,row:index%24+1,time:`${String(9+index%4).padStart(2,'0')}:${String(index*7%60).padStart(2,'0')}:00`,flightId:`FLT-${projectId}-${String([24,23,22][index%3]).padStart(3,'0')}`,description:descriptions[k],recommendation:recommendations[k],remarks:status==='Resolved'?'Demo follow-up recorded. Field verification complete.':'',assignee:['Site inspection team','Electrical maintenance','Module maintenance'][index%3],risk:[4,3,2,3,2,5,4,3][k],latitude:0,longitude:0,history:[{at:date+'T09:00:00Z',actor:'Inspection team',action:'Observation created',remarks:'Generated demo observation. Evidence is illustrative.'},...(status!=='Open'?[{at:date+'T14:30:00Z',actor:'Site engineer',action:`Status changed to ${status}`,remarks:status==='Resolved'?'Demo verification completed.':'Assigned for field review.'}]:[])]};
}
