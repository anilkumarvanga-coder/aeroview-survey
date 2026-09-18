import {Page,Query} from '../models';
export function paginate<T>(records:T[],q:Query):Page<T>{const size=q.size??10;const page=q.page??1;return {items:records.slice((page-1)*size,page*size),total:records.length}}
