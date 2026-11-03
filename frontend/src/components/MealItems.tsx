import { kcal } from "../lib/format";
import type { MealItem } from "../lib/types";

export function MealItems({ items }: { items: MealItem[] }) {
  return (
    <ul className="item-list">
      {items.map((item, i) => (
        <li key={`${item.name}-${i}`} className="item">
          <div className="item-main">
            <strong>{item.name}</strong>
            <span className="muted small">{item.quantity}</span>
            <div className="row gap-xs wrap">
              {item.is_low_confidence && (
                <span className="tag tag-warn" title="The AI wasn't sure about this item">
                  Unsure
                </span>
              )}
              {item.is_calorie_capped && (
                <span className="tag tag-warn" title="Calories were capped as unrealistically high">
                  Capped
                </span>
              )}
            </div>
          </div>
          <div className="item-nums">
            <strong>{kcal(item.approx_cal)}</strong>
            <span className="muted small">
              {item.protein ? `P ${item.protein}` : ""}
              {item.protein && item.fat ? " · " : ""}
              {item.fat ? `F ${item.fat}` : ""}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <div className="note note-warn">
      {warnings.map((w) => (
        <p key={w}>⚠️ {w}</p>
      ))}
    </div>
  );
}

export const SOURCE_LABEL: Record<string, string> = {
  photo: "📷 Photo",
  menu_template: "📅 Office menu",
};
