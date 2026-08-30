import { buildingsInCategory } from "../types/buildings";
import { ROUTES } from "../routing";

interface CategoryCard {
  path: string;
  title: string;
  description: string;
  count: number | null;
}

export default function CategoryHome({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const cards: CategoryCard[] = [
    {
      path: ROUTES.avatar,
      title: "Avatar",
      description: "Character, equipment, animations, and tools",
      count: null,
    },
    {
      path: ROUTES.buildings,
      title: "Buildings",
      description: "Construction stages, walls, castle, and environment",
      count: buildingsInCategory("buildings").length,
    },
    {
      path: ROUTES.workstations,
      title: "Workstations",
      description: "Crafting stations and assembly sequences",
      count: buildingsInCategory("workstations").length,
    },
    {
      path: ROUTES.creatures,
      title: "Creatures",
      description: "Dragons, farm animals, and creature clips",
      count: buildingsInCategory("creatures").length,
    },
  ];

  return (
    <div className="category-home">
      <div className="category-home-inner">
        <h1>3D Viewer</h1>
        <p className="category-home-sub">Choose a category</p>
        <div className="category-home-grid">
          {cards.map((card) => (
            <button
              key={card.path}
              type="button"
              className="category-home-card"
              onClick={() => navigate(card.path)}
            >
              <span className="category-home-card-title">{card.title}</span>
              <span className="category-home-card-desc">{card.description}</span>
              {card.count !== null && (
                <span className="category-home-card-count">
                  {card.count} {card.count === 1 ? "item" : "items"}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
