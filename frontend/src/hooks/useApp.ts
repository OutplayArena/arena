import { useContext } from "react";
import { AppContext, type AppContextValue } from "../state";

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
