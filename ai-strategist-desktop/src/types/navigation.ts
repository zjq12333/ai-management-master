export type Route =
  | "overview"
  | "loginRepair"
  | "enhancer"
  | "aiManagement"
  | "modelManagement"
  | "maintenance"
  | "settings";

export const ALL_APP_ROUTES: Route[] = [
  "overview",
  "loginRepair",
  "enhancer",
  "aiManagement",
  "modelManagement",
  "maintenance",
  "settings",
];

export function isAppRoute(value: string): value is Route {
  return (ALL_APP_ROUTES as string[]).includes(value);
}
