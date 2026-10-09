import {
  AgentActivityOpenButton,
  AgentActivityPanel,
} from "@/components/layout/AgentActivityPanel";
import { CameraHelp } from "@/components/layout/CameraHelp";
import { LensSwitcher } from "@/components/layout/LensSwitcher";
import { EntityInspector } from "@/components/twin/EntityInspector";
import { TwinIssuesNotice } from "@/components/twin/TwinIssuesNotice";
import { TwinStatusOverlay } from "@/components/twin/TwinStatusOverlay";
import { pickSource } from "@/core/twin/devSources";
import { useNetworkStatus } from "@/hooks/networkStatus.hook";
import { useProductParam } from "@/hooks/productParam.hook";
import { useTwinSource } from "@/hooks/twinSource.hook";
import { StoreScene } from "@/scene/StoreScene";

const source = pickSource();

export function TwinPage() {
  useTwinSource(source);
  useNetworkStatus();
  useProductParam();

  return (
    <>
      <main className="viewport relative">
        <StoreScene />
        <TwinStatusOverlay />
        {/* TODO(BE): the Revenue and Promotions lenses read GET /revenue and GET /promotions, which apps/api
          does not serve yet; until then they show their empty report and one toast. */}
        <div className="lens-switcher">
          <LensSwitcher />
        </div>
        <div className="absolute bottom-4 left-4 z-10">
          <CameraHelp />
        </div>
        <AgentActivityOpenButton />
        <EntityInspector />
        <TwinIssuesNotice />
      </main>
      <AgentActivityPanel />
    </>
  );
}
