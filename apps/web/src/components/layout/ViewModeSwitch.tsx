import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Segmented } from "@/components/commerce/Segmented";
import { LiveIcon, SimulationIcon } from "@/components/icons";
import { VIEW_MODE, type ViewMode } from "@/enums/ui.enum";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";

/**
 * Live / Simulation switch over the 3D view. Simulation can be picked only while a
 * simulation is open; when it closes (committed or discarded) the view goes back to Live.
 */
export function ViewModeSwitch() {
  const { t } = useTranslation();
  const viewMode = useUiStore((state) => state.viewMode);
  const setViewMode = useUiStore((state) => state.setViewMode);
  const open = useTwinStore((state) => state.simulation !== null);

  useEffect(() => {
    if (!open && viewMode === VIEW_MODE.Simulation) setViewMode(VIEW_MODE.Live);
  }, [open, viewMode, setViewMode]);

  return (
    <Segmented<ViewMode>
      variant="glass"
      label={t("viewMode.label")}
      layoutId="view-mode"
      value={open ? viewMode : VIEW_MODE.Live}
      onChange={setViewMode}
      options={[
        { value: VIEW_MODE.Live, label: t("viewMode.live"), icon: <LiveIcon className="h-3.5 w-3.5 shrink-0" /> },
        {
          value: VIEW_MODE.Simulation,
          label: open ? t("viewMode.simulation") : t("viewMode.noSimulation"),
          icon: <SimulationIcon className="h-3.5 w-3.5 shrink-0" />,
          disabled: !open,
        },
      ]}
    />
  );
}
