import { useCallback, useEffect, useState } from "react";

export const ROUTES = {
  home: "/",
  avatar: "/Avatar",
  buildings: "/Buildings",
  workstations: "/Workstations",
  creatures: "/Creatures",
} as const;

export type AppRoute = (typeof ROUTES)[keyof typeof ROUTES];

const KNOWN = new Set<string>(Object.values(ROUTES));

function canonicalize(pathname: string): AppRoute {
  let path = pathname;
  if (path.length > 1 && path.endsWith("/")) {
    path = path.slice(0, -1);
  }
  const lower = path.toLowerCase();
  for (const route of KNOWN) {
    if (route.toLowerCase() === lower) return route as AppRoute;
  }
  return ROUTES.home;
}

export function usePath(): {
  path: AppRoute;
  navigate: (to: string) => void;
} {
  const [path, setPath] = useState<AppRoute>(() =>
    canonicalize(window.location.pathname),
  );

  useEffect(() => {
    const canonical = canonicalize(window.location.pathname);
    if (window.location.pathname !== canonical) {
      window.history.replaceState({}, "", canonical);
    }
    setPath(canonical);

    const onPop = () => setPath(canonicalize(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to: string) => {
    const next = canonicalize(to);
    if (window.location.pathname !== next) {
      window.history.pushState({}, "", next);
    }
    setPath(next);
  }, []);

  return { path, navigate };
}
