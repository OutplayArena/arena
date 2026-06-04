const uiModules = import.meta.glob("@games/**/ui/*.tsx");

console.log("[registry] glob modules found:", Object.keys(uiModules));

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

async function loadComponent(
  gameSlug: string,
  name: string,
): Promise<ComponentModule | null> {
  console.log(`[registry] loadComponent looking for game="${gameSlug}" name="${name}"`);
  for (const [key, loader] of Object.entries(uiModules)) {
    const parsedSlug = parseGameSlug(key);
    const parsedName = parseComponentName(key);
    console.log(`[registry]   checking key="${key}" slug="${parsedSlug}" name="${parsedName}"`);
    if (parsedSlug === gameSlug && parsedName === name) {
      console.log(`[registry]   MATCH! loading...`);
      const mod = await loader();
      console.log(`[registry]   loaded successfully, has default:`, !!mod.default);
      return mod as ComponentModule;
    }
  }
  console.log(`[registry]   NO MATCH found for game="${gameSlug}" name="${name}"`);
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
