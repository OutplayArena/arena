import { useContext } from "react";
import { SiteConfigContext } from "../context/SiteConfigContext";

export function useSiteConfig() {
  return useContext(SiteConfigContext);
}
