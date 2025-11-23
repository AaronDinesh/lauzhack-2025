'use client';

import { useMemo } from 'react';

export type StatusTone = 'info' | 'success' | 'warning' | 'danger';

export interface StatusItem {
  id: string;
  label: string;
  detail?: string;
  tone?: StatusTone;
  ts?: number;
}

interface StatusDockProps {
  items: StatusItem[];
  recording?: boolean;
  onClear?: () => void;
}

const toneClasses: Record<StatusTone, string> = {
  info: 'border-blue-500/60 bg-blue-500/10 text-blue-100',
  success: 'border-green-500/60 bg-green-500/10 text-green-100',
  warning: 'border-yellow-400/60 bg-yellow-500/10 text-yellow-100',
  danger: 'border-red-500/60 bg-red-500/10 text-red-100',
};

export function StatusDock({ items, recording, onClear }: StatusDockProps) {
  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => (b.ts || 0) - (a.ts || 0)).slice(0, 5),
    [items]
  );

  return (
    <div className="fixed left-4 bottom-4 z-[5000] w-80 max-w-[90vw] pointer-events-none">
      <div className="bg-black/70 backdrop-blur-lg rounded-xl border border-gray-800 shadow-lg overflow-hidden pointer-events-auto">
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800">
          <div className="flex items-center gap-2 text-sm text-gray-200">
            <span className="text-base">� Status</span>
            {recording && (
              <span className="flex items-center gap-1 text-red-300 text-xs">
                <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                Recording
              </span>
            )}
          </div>
          {onClear && (
            <button
              className="text-xs text-gray-400 hover:text-gray-200 transition"
              onClick={onClear}
            >
              Clear
            </button>
          )}
        </div>

        <div className="max-h-64 overflow-y-auto p-3 flex flex-col gap-2">
          {sorted.length === 0 && (
            <div className="text-xs text-gray-500">Awaiting actions…</div>
          )}
          {sorted.map((item) => (
            <div
              key={item.id}
              className={`rounded-lg border px-3 py-2 text-sm ${toneClasses[item.tone || 'info']}`}
            >
              <div className="font-semibold text-sm">{item.label}</div>
              {item.detail && (
                <div className="text-xs text-gray-200/80 break-words mt-1">
                  {item.detail}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default StatusDock;
