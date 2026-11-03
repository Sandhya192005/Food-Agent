import { useEffect, useState } from "react";

import { apiBlob } from "../lib/api";
import type { MealDetail } from "../lib/types";

/**
 * The meal's photo. S3 photos load straight from the signed link in `image_url`.
 * Local photos (or an expired S3 link) are fetched through GET /meals/{id}/image.
 */
export function MealPhoto({ meal }: { meal: MealDetail }) {
  const [useApi, setUseApi] = useState(!meal.image_url);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!meal.has_image || !useApi) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    apiBlob(`/meals/${meal.id}/image`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [meal.id, meal.has_image, useApi]);

  if (!meal.has_image) return null;
  if (failed) return <p className="muted small meal-photo-missing">📷 Couldn't load the photo.</p>;

  const src = useApi ? blobUrl : meal.image_url;
  return (
    <div className="meal-photo">
      {src ? (
        <img
          src={src}
          alt={meal.title ?? "Meal photo"}
          // A signed S3 link stops working after a few minutes: fall back to the API.
          onError={() => (useApi ? setFailed(true) : setUseApi(true))}
        />
      ) : (
        <div className="meal-photo-loading muted small">Loading photo…</div>
      )}
    </div>
  );
}
