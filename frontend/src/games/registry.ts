const uiModules = import.meta.glob("@games/**/ui/*.tsx");

type ComponentModule = { default: React.ComponentType<unknown> };

function parseGameSlug(key: string): string {
  const parts = key.split("/");
  const uiIdx = parts.indexOf("ui");
  if (uiIdx === -1 || uiIdx === 0) return "";
  return parts[uiIdx - 1] ?? "";
}

function parseComponentName(key: string): string {
  const basename = key.split("/").pop() ?? "";
  return basename.replace(".tsx", "");
}

export function hasCustomUI(gameSlug: string): boolean {
  for (const key of Object.keys(uiModules)) {
    if (parseGameSlug(key) === gameSlug) return true;
  }
  return false;
}

async function loadComponent(
  gameSlug: string,
  name: string,
): Promise<ComponentModule | null> {
  for (const [key, loader] of Object.entries(uiModules)) {
    if (parseGameSlug(key) === gameSlug && parseComponentName(key) === name) {
      return (await loader()) as ComponentModule;
    }
  }
  return null;
}

export async function loadLiveView(
  gameSlug: string,
): Promise<ComponentModule | null> {
  return loadComponent(gameSlug, "LiveView");
}

export async function loadConfigForm(
  gameSlug: string,
): Promise<ComponentModule | null> {
  return loadComponent(gameSlug, "ConfigForm");
}

export async function loadHistoryView(
  gameSlug: string,
): Promise<ComponentModule | null> {
  return loadComponent(gameSlug, "HistoryView");
}
