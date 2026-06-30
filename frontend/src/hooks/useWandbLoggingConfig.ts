import { useEffect, useState } from "react";
import { getWandbKeyStatus, getWandbEntities } from "../api";

export interface WandbLoggingState {
  enabled: boolean;
  entity: string;
  project: string;
  runName: string;
  // Populated from the entities endpoint once a key is configured.
  availableEntities: string[];
  keyConfigured: boolean;
  entitiesLoading: boolean;
}

export interface WandbLoggingSetters {
  setEnabled: (v: boolean) => void;
  setEntity: (v: string) => void;
  setProject: (v: string) => void;
  setRunName: (v: string) => void;
}

export interface UseWandbLoggingConfigResult extends WandbLoggingState, WandbLoggingSetters {
  /** Fields to merge into the experiment-creation payload when enabled. */
  toConfigFields(): Record<string, unknown>;
}

export function useWandbLoggingConfig(): UseWandbLoggingConfigResult {
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [availableEntities, setAvailableEntities] = useState<string[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [entity, setEntity] = useState("");
  const [project, setProject] = useState("outplayarena");
  const [runName, setRunName] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await getWandbKeyStatus();
        if (cancelled) return;
        setKeyConfigured(status.configured);

        if (status.configured) {
          setEntitiesLoading(true);
          try {
            const data = await getWandbEntities();
            if (!cancelled) {
              setAvailableEntities(data.entities);
              if (!entity) setEntity(data.personal_entity);
            }
          } catch {
            // Entity fetch failure is non-fatal — user can type manually.
          } finally {
            if (!cancelled) setEntitiesLoading(false);
          }
        }
      } catch {
        // Key status failure is silent — treat as not configured.
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toConfigFields = (): Record<string, unknown> => {
    if (!enabled) return {};
    const fields: Record<string, unknown> = { wandb_logging: true };
    if (project && project !== "outplayarena") fields.wandb_project = project;
    else fields.wandb_project = "outplayarena";
    if (entity) fields.wandb_entity = entity;
    if (runName) fields.wandb_run_name = runName;
    return fields;
  };

  return {
    enabled, setEnabled,
    entity, setEntity,
    project, setProject,
    runName, setRunName,
    availableEntities,
    keyConfigured,
    entitiesLoading,
    toConfigFields,
  };
}
