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

/** "12.5 g" -> 12.5; missing values count as 0. */
function grams(value: string | null): number {
  return value ? parseFloat(value) || 0 : 0;
}

/** Totals for the whole meal: calories, protein and fat. */
export function NutritionTotals({ items, calories }: { items: MealItem[]; calories: number | null }) {
  const protein = items.reduce((sum, i) => sum + grams(i.protein), 0);
  const fat = items.reduce((sum, i) => sum + grams(i.fat), 0);
  const hasProtein = items.some((i) => i.protein);
  const hasFat = items.some((i) => i.fat);
  const fmt = (g: number) => `${Math.round(g * 10) / 10} g`;
  return (
    <div className="nutrition-totals">
      <div>
        <strong>{kcal(calories)}</strong>
        <span className="muted small">Calories</span>
      </div>
      <div>
        <strong>{hasProtein ? fmt(protein) : "—"}</strong>
        <span className="muted small">Protein</span>
      </div>
      <div>
        <strong>{hasFat ? fmt(fat) : "—"}</strong>
        <span className="muted small">Fat</span>
      </div>
      <div>
        <strong>{items.length}</strong>
        <span className="muted small">Item{items.length === 1 ? "" : "s"}</span>
      </div>
    </div>
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
