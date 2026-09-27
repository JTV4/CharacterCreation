import { useState } from 'react';
import palette from '../data/appearance.json';
export type AppearanceSex = 'Male' | 'Female';
export interface AppearanceOptions {skin: string; eyes: string; hair: string; hairColor: string; beardStyle: string; mustacheStyle: string; eyebrowStyle: string; eyelashStyle: string; gazeX: number; gazeY: number; demo: boolean}
const defaults: AppearanceOptions = {skin:'warm_beige',eyes:'brown',hair:'none',hairColor:'brown',beardStyle:'none',mustacheStyle:'none',eyebrowStyle:'natural',eyelashStyle:'subtle',gazeX:0,gazeY:0,demo:false};
const storageKey='grindscape.rework.appearance.v1';
function read():Record<AppearanceSex,AppearanceOptions>{
 let data:any={};try{data=JSON.parse(localStorage.getItem(storageKey)??'{}')}catch{}
 const result={} as Record<AppearanceSex,AppearanceOptions>;
 for(const sex of ['Male','Female'] as const){const value=data?.[sex]??{};result[sex]={...defaults,
 skin:palette.skinTones.some(x=>x.id===value.skin)?value.skin:defaults.skin,
 eyes:palette.eyes.some(x=>x.id===value.eyes)?value.eyes:defaults.eyes,
 hair:palette.hairStyles[sex].includes(value.hair)?value.hair:(({crop:'buzz_cut',swept:'short',tied:'ponytail',bob:'short'} as Record<string,string>)[value.hair]??'none'),
 beardStyle:sex==='Male'&&palette.beardStyles.some(x=>x.id===value.beardStyle)?value.beardStyle:'none',
 mustacheStyle:sex==='Male'&&palette.mustacheStyles.some(x=>x.id===value.mustacheStyle)?value.mustacheStyle:'none',
 eyebrowStyle:palette.eyebrowStyles.some(x=>x.id===value.eyebrowStyle)?value.eyebrowStyle:defaults.eyebrowStyle,
 eyelashStyle:palette.eyelashStyles.some(x=>x.id===value.eyelashStyle)?value.eyelashStyle:defaults.eyelashStyle,
 hairColor:palette.hairColors.some(x=>x.id===value.hairColor)?value.hairColor:defaults.hairColor};}
 return result;
}
export function useAppearanceOptions(){
 const [options,setOptions]=useState(read);
 const update=(sex:AppearanceSex,patch:Partial<AppearanceOptions>)=>setOptions(old=>{
 const next={...old,[sex]:{...old[sex],...patch}};try{localStorage.setItem(storageKey,JSON.stringify(next))}catch{}return next;});
 return {options,update};
}
export default function AppearancePanel({sex,value,onChange,error}:{sex:AppearanceSex;value:AppearanceOptions;onChange:(patch:Partial<AppearanceOptions>)=>void;error:string|null}){
 return <details className="appearance-panel" open><summary>{sex} appearance</summary>
 <label>Skin tone<select aria-label="Skin tone" value={value.skin} onChange={e=>onChange({skin:e.target.value})}>{palette.skinTones.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
 <label>Eye color<select aria-label="Eye color" value={value.eyes} onChange={e=>onChange({eyes:e.target.value})}>{palette.eyes.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
 <label>Eyebrows<select aria-label="Eyebrows" value={value.eyebrowStyle} onChange={e=>onChange({eyebrowStyle:e.target.value})}>{palette.eyebrowStyles.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
 <label>Eyelashes<select aria-label="Eyelashes" value={value.eyelashStyle} onChange={e=>onChange({eyelashStyle:e.target.value})}>{palette.eyelashStyles.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
 <label>Hairstyle<select aria-label="Hairstyle" value={value.hair} onChange={e=>onChange({hair:e.target.value})}><option value="none">No hair</option>{palette.hairStyles[sex].map(id=><option key={id} value={id}>{id.split('_').map(word=>word[0].toUpperCase()+word.slice(1)).join(' ')}</option>)}</select></label>
 {sex==='Male'&&<><p>Beard and mustache are separate choices. Choose None for either.</p><label>Beard<select aria-label="Beard" value={value.beardStyle} onChange={e=>onChange({beardStyle:e.target.value})}>{palette.beardStyles.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
 <label>Mustache<select aria-label="Mustache" value={value.mustacheStyle} onChange={e=>onChange({mustacheStyle:e.target.value})}>{palette.mustacheStyles.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label></>}
 <label>Hair color<select aria-label="Hair color" value={value.hairColor} onChange={e=>onChange({hairColor:e.target.value})}>{palette.hairColors.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
 <label>Look left / right<input aria-label="Look left / right" type="range" min="-1" max="1" step=".01" value={value.gazeX} onChange={e=>onChange({gazeX:+e.target.value,demo:false})}/></label>
 <label>Look down / up<input aria-label="Look down / up" type="range" min="-1" max="1" step=".01" value={value.gazeY} onChange={e=>onChange({gazeY:+e.target.value,demo:false})}/></label>
 <label><input type="checkbox" checked={value.demo} onChange={e=>onChange({demo:e.target.checked})}/> Demonstrate eye movement</label>
 <button onClick={()=>onChange({gazeX:0,gazeY:0,demo:false})}>Center eyes</button>
 <p>Appearance choices are saved for this character. Eyebrows match the hair color. Choose No hair when using a fitted hat.</p>{error&&<p role="alert">{error}</p>}
 </details>;
}
