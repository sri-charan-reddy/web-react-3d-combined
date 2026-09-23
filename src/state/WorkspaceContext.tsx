/**
 * Workspace UI state — currently just the active viewport tab.
 *
 * Zoom used to live here as a page-wide CSS scale. It moved into the arena's
 * own camera (`render/camera.ts`), which is where map zoom belongs: the page
 * scale duplicated the browser's own Cmd +/- and broke the layout at both ends
 * of its range.
 */
import {
  createContext,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react';

export type ViewMode = 'arena' | 'orbit' | 'sensor' | 'camera';

interface WorkspaceValue {
  view: ViewMode;
  setView: (mode: ViewMode) => void;
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function WorkspaceProvider({ children }: PropsWithChildren) {
  const [view, setView] = useState<ViewMode>('arena');
  const value = useMemo<WorkspaceValue>(() => ({ view, setView }), [view]);
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used inside <WorkspaceProvider>');
  return ctx;
}
