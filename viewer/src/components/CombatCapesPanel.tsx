import { useState } from 'react';
import styles from '../data/combatCapes.json';
import seasonal from '../data/seasonalCapes.json';
import type { EquipmentState } from '../types/equipment';
import type { AppearanceSex } from './AppearancePanel';
import './CombatCapesPanel.css';

type Part = 'cape' | 'helmet';
const families = ['Ranged', 'Mage', 'Melee'];
export default function CombatCapesPanel({ sex, state, onChoose }: {
  sex: AppearanceSex;
  state: EquipmentState;
  onChoose: (part: Part, id: string) => void;
}) {
  const [family, setFamily] = useState('Ranged');
  const id = (style: string, part: Part) => `combat_${style}_${sex.toLowerCase()}_${part}`;
  const seasonalId = (style: string) => `seasonal_${style}_${sex.toLowerCase()}_cape`;
  const selected = (part: Part) => styles.find(s => state[id(s.id, part)])?.id ??
    (part === 'cape' ? seasonal.find(s => state[seasonalId(s.id)])?.id ?? '' : '');
  return <details className="combat-capes-panel" open>
    <summary>Capes &amp; hoods</summary>
    <p>Choose a cape, or mix a combat cape and hood. Seasonal capes keep your current hat.</p>
    <div className="cape-families" role="group" aria-label="Combat cape styles">
      {[...families, 'Seasonal'].map(f => <button key={f} type="button" aria-pressed={f === family} onClick={() => setFamily(f)}>{f}</button>)}
    </div>
    <div className="cape-sets">{family === 'Seasonal' ? seasonal.map(s => <button key={s.id} type="button"
      aria-pressed={selected('cape') === s.id} title={`Wear ${s.name} cape`}
      onClick={() => onChoose('cape', seasonalId(s.id))}>
      <img src={`/equipment/SeasonalCapes/previews/${sex}_${s.id}.webp?v=3`} alt="" loading="lazy" />
      <span>{s.holiday} · {s.name}</span>
    </button>) : styles.filter(s => s.family === family).map(s => <button key={s.id} type="button"
      aria-pressed={selected('cape') === s.id && selected('helmet') === s.id}
      title={`Wear ${s.name} cape and hood`}
      onClick={() => { onChoose('cape', id(s.id, 'cape')); onChoose('helmet', id(s.id, 'helmet')); }}>
      <img src={`/equipment/CombatCapes/previews/${sex}_${s.id}.webp?v=30260927-flow3`} alt="" loading="lazy" />
      <span>{s.name}</span>
    </button>)}</div>
    {([{ part: 'cape', label: 'Cape' }, { part: 'helmet', label: 'Hood' }] as const).map(({ part, label }) =>
      <label key={part}>{label}<select aria-label={`Combat ${label.toLowerCase()}`} value={selected(part)}
        onChange={e => onChoose(part, e.target.value ? (part === 'cape' && seasonal.some(s => s.id === e.target.value) ? seasonalId(e.target.value) : id(e.target.value, part)) : '')}>
        <option value="">No {label.toLowerCase()}</option>
        {families.map(f => <optgroup label={f} key={f}>{styles.filter(s => s.family === f).map(s => <option value={s.id} key={s.id}>{s.name}</option>)}</optgroup>)}
        {part === 'cape' && <optgroup label="Seasonal">{seasonal.map(s => <option value={s.id} key={s.id}>{s.holiday} · {s.name}</option>)}</optgroup>}
      </select></label>)}
    <p>Hoods cover your hairstyle while worn. Capes flow with movement and gravity. Seasonal capes shimmer with animated sparkles.</p>
  </details>;
}
