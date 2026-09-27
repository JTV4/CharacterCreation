import styles from '../data/starterClothes.json';
import type { EquipmentSlot, EquipmentState, WearSlot } from '../types/equipment';
import type { AppearanceSex } from './AppearancePanel';
import './StarterClothesPanel.css';

export const CLOTHING_PARTS = [
  { piece: 'upperbody', wear: 'top', label: 'Top' },
  { piece: 'lowerbody', wear: 'bottom', label: 'Bottoms' },
  { piece: 'boots', wear: 'boots', label: 'Footwear' },
] as const;
const storageKey = 'grindscape.starter-clothes.v1';
export function starterId(style: string, sex: AppearanceSex, piece: string) {
  return `starter_${style}_${sex.toLowerCase()}_${piece}`;
}
export function restoreStarterClothes(initial: EquipmentState): EquipmentState {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
    if (Array.isArray(saved)) for (const id of saved) {
      if (typeof id === 'string' && id.startsWith('starter_') && id in initial) initial[id] = true;
    }
  } catch { /* Clothing remains optional when storage is unavailable. */ }
  return initial;
}
export function saveStarterClothes(state: EquipmentState) {
  try { localStorage.setItem(storageKey, JSON.stringify(Object.keys(state).filter(id => id.startsWith('starter_') && state[id]))); } catch { /* Private browser storage may be unavailable. */ }
}
export function chooseStarterClothes(state: EquipmentState, slots: EquipmentSlot[], sex: AppearanceSex, style: string, only?: WearSlot): EquipmentState {
  const next = { ...state };
  const gender = `${sex.toLowerCase()}_rework`;
  const wear = new Set<string>(only ? [only] : ['top', 'bottom', 'boots', 'helmet', 'gloves', 'cape', 'amulet']);
  for (const slot of slots) {
    if (slot.wear_slot && wear.has(slot.wear_slot) && (!slot.gender || slot.gender === gender)) next[slot.id] = false;
  }
  for (const part of CLOTHING_PARTS) {
    if (!only || part.wear === only) {
      const id = starterId(style, sex, part.piece);
      if (style && slots.some(slot => slot.id === id)) next[id] = true;
    }
  }
  return next;
}
const descriptions: Record<string, string> = {
  homestead: 'Fitted linen · ankle-length trousers', dockhand: 'Rolled sleeves · fitted trousers',
  woodland: 'Long tunic · soft leather boots', townsfolk: 'Waistcoat · tailored separates',
  artisan: 'Work shirt · leather apron', wayfarer: 'Travel vest · sturdy boots',
};
export default function StarterClothesPanel({ sex, state, onChoose }: {
  sex: AppearanceSex; state: EquipmentState; onChoose: (style: string, only?: WearSlot) => void;
}) {
  const selected = (piece: string) => styles.find(s => state[starterId(s.id, sex, piece)])?.id ?? '';
  return <details className="starter-clothes-panel" open>
    <summary>Starter clothes</summary>
    <p>Choose an everyday outfit, or mix separate pieces.</p>
    <div className="starter-outfits">{styles.map(style => {
      const active = CLOTHING_PARTS.every(p => selected(p.piece) === style.id);
      return <button key={style.id} type="button" className={active ? 'selected' : ''} aria-pressed={active} onClick={() => onChoose(style.id)} title={descriptions[style.id]}>
        <img src={`/equipment/StarterClothes/previews/${sex}_${style.id}.webp`} alt="" loading="lazy" />
        <span>{style.name}</span>
      </button>;
    })}</div>
    {CLOTHING_PARTS.map(part => <label key={part.piece}>{part.label}
      <select aria-label={`Starter ${part.label.toLowerCase()}`} value={selected(part.piece)} onChange={e => onChoose(e.target.value, part.wear)}>
        <option value="">No starter {part.label.toLowerCase()}</option>
        {styles.map(style => <option key={style.id} value={style.id}>{part.piece === 'boots' ? `${style.name} · ${style.footwear}` : style.name}</option>)}
      </select>
    </label>)}
    <p>Your clothing choices are saved separately for each character.</p>
  </details>;
}
