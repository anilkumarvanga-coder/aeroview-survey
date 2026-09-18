'use client';
import {Select,SelectTrigger,SelectValue,SelectContent,SelectItem} from '@/components/ui/select';
import {Progress} from '@/components/ui/progress';
export function Choice({value,onChange,options,label}:{value:string;onChange:(v:string)=>void;options:{value:string;label:string}[];label:string}){return <Select value={value} onValueChange={onChange}><SelectTrigger aria-label={label}><SelectValue/></SelectTrigger><SelectContent>{options.map(o=><SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent></Select>}
export function Badge({children}:{children:React.ReactNode}){const s=String(children);return <span className={'badge '+(/Critical|High|Open|Attention/.test(s)?'orange':/Completed|Good|Resolved|Active|Ready/.test(s)?'green':'neutral')}>{children}</span>}
export function Meter({value}:{value:number}){return <Progress value={value} aria-label={`${value}% complete`}/>}
